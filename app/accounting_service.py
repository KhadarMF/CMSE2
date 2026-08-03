"""Phase 20A/20B - Accounting engine.

All journal creation goes through create_journal_entry() so the two
invariants hold everywhere: entries must balance, and posted entries are
immutable (corrections happen via create_reversal, never edits).
"""
from datetime import datetime, date

from flask import current_app
from sqlalchemy import func

from app import db
from app.models import (
    Account, JournalEntry, JournalLine, AccountMapping,
    ACCOUNTING_BASE_CURRENCY,
    PAYMENT_REQUEST_CATEGORIES, PROJECT_PAYMENT_METHODS,
)
from app.settings import get_setting

SLSH_RATE_SETTING_KEY = "ACC_SLSH_PER_USD"

# code, name, type, is_system
DEFAULT_ACCOUNTS = [
    # Assets
    ("1000", "Cash on Hand", "Asset", True),
    ("1010", "Zaad Account", "Asset", True),
    ("1020", "E-Dahab Account", "Asset", True),
    ("1030", "Bank Account", "Asset", True),
    ("1100", "Accounts Receivable", "Asset", True),
    ("1200", "Inventory", "Asset", False),
    ("1500", "Equipment & Fixed Assets", "Asset", False),
    # Liabilities
    ("2000", "Accounts Payable", "Liability", True),
    ("2100", "Loans Payable", "Liability", False),
    # Equity
    ("3000", "Owner's Equity", "Equity", True),
    ("3100", "Opening Balance Equity", "Equity", True),
    # Income
    ("4000", "Sales Revenue", "Income", True),
    ("4100", "Service Revenue", "Income", False),
    ("4900", "Other Income", "Income", False),
    # Expenses
    ("5000", "Cost of Goods Sold", "Expense", False),
    ("5100", "Materials & Supplies Expense", "Expense", True),
    ("5150", "Project Expenses", "Expense", True),
    ("5200", "Utilities Expense", "Expense", True),
    ("5250", "Rent Expense", "Expense", True),
    ("5300", "Salaries & Wages Expense", "Expense", True),
    ("5350", "Transport & Fuel Expense", "Expense", True),
    ("5400", "Professional Services Expense", "Expense", True),
    ("5450", "Equipment Expense", "Expense", True),
    ("5900", "General & Other Expenses", "Expense", True),
]

# Which seeded account each payment-request category books to
DEFAULT_CATEGORY_MAPPINGS = {
    "Materials & Supplies": "5100",
    "Project Expense": "5150",
    "Utilities": "5200",
    "Rent": "5250",
    "Salaries & Wages": "5300",
    "Transport & Fuel": "5350",
    "Professional Services": "5400",
    "Equipment": "5450",
    "Other": "5900",
}

# Which seeded account each payment method credits
DEFAULT_METHOD_MAPPINGS = {
    "Cash": "1000",
    "Zaad": "1010",
    "E-Dahab": "1020",
    "Bank Transfer": "1030",
    "Cheque": "1030",
    "Other": "1000",
}

DEFAULT_SPECIAL_MAPPINGS = {
    "payroll_salaries": "5300",
}


def ensure_default_accounts():
    """Seed the chart of accounts and default mappings once. Safe to call
    repeatedly; only fills gaps, never overwrites what an accountant has
    customized."""
    created = False
    by_code = {}
    for code, name, acc_type, is_system in DEFAULT_ACCOUNTS:
        acct = Account.query.filter_by(code=code).first()
        if not acct:
            acct = Account(code=code, name=name, account_type=acc_type, is_system=is_system)
            db.session.add(acct)
            created = True
        by_code[code] = acct
    if created:
        db.session.flush()

    def ensure_mapping(mapping_type, key, code):
        nonlocal created
        existing = AccountMapping.query.filter_by(mapping_type=mapping_type, key=key).first()
        if not existing:
            acct = by_code.get(code) or Account.query.filter_by(code=code).first()
            if acct:
                db.session.add(AccountMapping(mapping_type=mapping_type, key=key, account_id=acct.id))
                created = True

    for key, code in DEFAULT_CATEGORY_MAPPINGS.items():
        ensure_mapping("payment_category", key, code)
    for key, code in DEFAULT_METHOD_MAPPINGS.items():
        ensure_mapping("payment_method", key, code)
    for key, code in DEFAULT_SPECIAL_MAPPINGS.items():
        ensure_mapping("special", key, code)

    if created:
        db.session.commit()


def get_mapped_account(mapping_type, key, fallback_code=None):
    m = AccountMapping.query.filter_by(mapping_type=mapping_type, key=key).first()
    if m and m.account and m.account.is_active:
        return m.account
    if fallback_code:
        return Account.query.filter_by(code=fallback_code).first()
    return None


def get_slsh_rate():
    """SLSH units per 1 USD, from System Settings. Returns None if unset -
    callers must handle that (SLSH auto-journals are skipped with a warning
    rather than booked at a made-up rate)."""
    raw = get_setting(SLSH_RATE_SETTING_KEY, "")
    try:
        rate = float(raw)
        return rate if rate > 0 else None
    except (TypeError, ValueError):
        return None


def create_journal_entry(entry_date, lines, memo=None, reference=None,
                         source_module=None, source_record_id=None,
                         currency="USD", exchange_rate=1.0, original_amount=None,
                         created_by_id=None, post=False, posted_by_id=None):
    """The only way journal entries are created, manual or automated.

    lines: list of dicts {account_id, debit, credit, description}.
    Amounts must already be in USD. Validation:
      - at least 2 lines
      - each line has exactly one of debit/credit > 0
      - all accounts exist and are active
      - if post=True, total debits == total credits (within 0.01)
    Raises ValueError on any violation; nothing is written in that case.
    """
    if not lines or len(lines) < 2:
        raise ValueError("A journal entry needs at least two lines.")

    prepared = []
    for i, ln in enumerate(lines):
        debit = round(float(ln.get("debit") or 0), 2)
        credit = round(float(ln.get("credit") or 0), 2)
        if debit < 0 or credit < 0:
            raise ValueError(f"Line {i + 1}: amounts cannot be negative.")
        if (debit > 0) == (credit > 0):
            raise ValueError(f"Line {i + 1}: each line must have either a debit or a credit, not both and not neither.")
        account = db.session.get(Account, int(ln["account_id"]))
        if not account:
            raise ValueError(f"Line {i + 1}: account not found.")
        if not account.is_active:
            raise ValueError(f"Line {i + 1}: account {account.code} {account.name} is inactive.")
        prepared.append({"account_id": account.id, "debit": debit, "credit": credit,
                         "description": (ln.get("description") or "").strip() or None})

    total_debit = round(sum(l["debit"] for l in prepared), 2)
    total_credit = round(sum(l["credit"] for l in prepared), 2)
    if post and abs(total_debit - total_credit) >= 0.01:
        raise ValueError(f"Entry does not balance: debits {total_debit:,.2f} vs credits {total_credit:,.2f}.")

    entry = JournalEntry(
        entry_date=entry_date or date.today(),
        memo=memo, reference=reference,
        source_module=source_module, source_record_id=source_record_id,
        currency=currency or "USD", exchange_rate=exchange_rate or 1.0,
        original_amount=original_amount,
        created_by_id=created_by_id,
        status="Draft",
    )
    db.session.add(entry)
    db.session.flush()
    entry.entry_no = f"JE-{entry.entry_date.strftime('%Y%m%d')}-{entry.id:06d}"

    for order, ln in enumerate(prepared):
        db.session.add(JournalLine(journal_entry_id=entry.id, line_order=order, **ln))

    if post:
        entry.status = "Posted"
        entry.posted_by_id = posted_by_id or created_by_id
        entry.posted_at = datetime.utcnow()

    return entry


def post_entry(entry, posted_by_id=None):
    if entry.status != "Draft":
        raise ValueError(f"Only Draft entries can be posted; this entry is {entry.status}.")
    if not entry.is_balanced:
        raise ValueError(f"Entry does not balance: debits {entry.total_debit:,.2f} vs credits {entry.total_credit:,.2f}.")
    if len(entry.lines) < 2:
        raise ValueError("A journal entry needs at least two lines.")
    entry.status = "Posted"
    entry.posted_by_id = posted_by_id
    entry.posted_at = datetime.utcnow()
    return entry


def create_reversal(entry, reason, created_by_id=None):
    """The only correct way to undo a Posted entry: a new Posted entry with
    debits and credits swapped, linked in both directions. The original is
    marked Reversed but its lines are untouched - the audit trail shows both."""
    if entry.status != "Posted":
        raise ValueError(f"Only Posted entries can be reversed; this entry is {entry.status}.")
    if entry.reversed_by_entry_id:
        raise ValueError("This entry has already been reversed.")
    if not (reason or "").strip():
        raise ValueError("A reversal reason is required.")

    reversal = create_journal_entry(
        entry_date=date.today(),
        lines=[{"account_id": l.account_id, "debit": l.credit, "credit": l.debit,
                "description": l.description} for l in entry.lines],
        memo=f"Reversal of {entry.entry_no}: {reason.strip()}",
        reference=entry.reference,
        source_module=entry.source_module, source_record_id=entry.source_record_id,
        currency=entry.currency, exchange_rate=entry.exchange_rate,
        original_amount=entry.original_amount,
        created_by_id=created_by_id, post=True, posted_by_id=created_by_id,
    )
    db.session.flush()
    entry.status = "Reversed"
    entry.reversed_by_entry_id = reversal.id
    reversal.reverses_entry_id = entry.id
    return reversal


def account_balance(account_id, up_to=None):
    """Net balance of an account from Posted entries (Reversed originals and
    their reversals both count - they cancel out, which is the point).
    Returned in the account's natural sign: positive means the balance sits
    on the account's normal side."""
    q = db.session.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry).filter(
        JournalLine.account_id == account_id,
        JournalEntry.status.in_(["Posted", "Reversed"]),
    )
    if up_to:
        q = q.filter(JournalEntry.entry_date <= up_to)
    debits, credits = q.one()
    account = db.session.get(Account, account_id)
    net = float(debits) - float(credits)
    if account and account.normal_side == "credit":
        net = -net
    return round(net, 2)


def _usd_amount_and_meta(amount, currency):
    """Convert a transaction amount to USD for the ledger. Returns
    (usd_amount, currency, rate, original_amount) or raises ValueError if
    the currency is SLSH and no rate is configured."""
    currency = (currency or "USD").upper()
    if currency == ACCOUNTING_BASE_CURRENCY:
        return round(float(amount), 2), currency, 1.0, None
    if currency == "SLSH":
        rate = get_slsh_rate()
        if not rate:
            raise ValueError(
                "No SLSH exchange rate is configured. Set 'SLSH per USD' in "
                "Accounting > Mappings & Settings, then create the journal entry manually."
            )
        return round(float(amount) / rate, 2), currency, rate, round(float(amount), 2)
    raise ValueError(f"Unsupported currency for the ledger: {currency}")


def journal_for_payment_request_payment(pr, payment, created_by_id=None):
    """Auto-journal for a Payment Request payment (Phase 19 module):
    Debit the expense account mapped to the request's category,
    Credit the asset account mapped to the payment method."""
    expense = get_mapped_account("payment_category", pr.category or "Other", fallback_code="5900")
    asset = get_mapped_account("payment_method", payment.payment_method or "Cash", fallback_code="1000")
    if not expense or not asset:
        raise ValueError("Category or payment-method account mapping is missing; check Accounting > Mappings.")

    usd, currency, rate, original = _usd_amount_and_meta(payment.amount, payment.currency or pr.currency)
    desc = f"{pr.request_no} - {pr.payee_name}"
    return create_journal_entry(
        entry_date=payment.payment_date or date.today(),
        lines=[
            {"account_id": expense.id, "debit": usd, "credit": 0, "description": desc},
            {"account_id": asset.id, "debit": 0, "credit": usd, "description": f"{payment.payment_method} {payment.reference_no or ''}".strip()},
        ],
        memo=f"Payment for {pr.request_no}: {pr.purpose}",
        reference=payment.reference_no,
        source_module="payment-requests", source_record_id=payment.id,
        currency=currency, exchange_rate=rate, original_amount=original,
        created_by_id=created_by_id, post=True, posted_by_id=created_by_id,
    )


def journal_for_payroll_payment(entry, payment, created_by_id=None):
    """Auto-journal for a Project Payroll payment:
    Debit Salaries & Wages, Credit the asset account for the method.
    Payroll amounts are USD (the payroll module has no currency field)."""
    salaries = get_mapped_account("special", "payroll_salaries", fallback_code="5300")
    asset = get_mapped_account("payment_method", payment.payment_method or "Cash", fallback_code="1000")
    if not salaries or not asset:
        raise ValueError("Payroll or payment-method account mapping is missing; check Accounting > Mappings.")

    usd = round(float(payment.amount), 2)
    employee_name = entry.employee.full_name if getattr(entry, "employee", None) else f"entry {entry.id}"
    project_name = entry.batch.project.project_name if getattr(entry, "batch", None) and getattr(entry.batch, "project", None) else ""
    return create_journal_entry(
        entry_date=payment.payment_date or date.today(),
        lines=[
            {"account_id": salaries.id, "debit": usd, "credit": 0, "description": f"Payroll - {employee_name} {project_name}".strip()},
            {"account_id": asset.id, "debit": 0, "credit": usd, "description": f"{payment.payment_method} {payment.reference_no or ''}".strip()},
        ],
        memo=f"Payroll payment - {employee_name}" + (f" ({project_name})" if project_name else ""),
        reference=payment.reference_no,
        source_module="payroll", source_record_id=payment.id,
        created_by_id=created_by_id, post=True, posted_by_id=created_by_id,
    )


def try_auto_journal(builder, *args, created_by_id=None):
    """Wrapper used by route hooks. The business record (payment) is the
    source of truth and has already been committed - a journal failure must
    never undo it. Returns (entry, error_message); exactly one is None.
    On failure the session is rolled back and the caller shows a warning so
    the accountant can create the entry manually."""
    try:
        entry = builder(*args, created_by_id=created_by_id)
        db.session.commit()
        return entry, None
    except Exception as exc:
        db.session.rollback()
        try:
            current_app.logger.warning("Auto-journal failed: %s", exc)
        except Exception:
            pass
        return None, str(exc)


# ---------------------------------------------------------------------------
# Phase 20C - Reports + Opening Balances
#
# No new tables. Every report is computed from posted journal entries, and
# opening balances are a normal posted journal entry (source_module
# "opening-balances") whose balancing line goes to Opening Balance Equity.
# The immutability rule means these reports can be trusted: nothing they
# read can be silently edited after the fact.
# ---------------------------------------------------------------------------

OPENING_BALANCE_SOURCE = "opening-balances"


def _posted_line_sums(account_id, start=None, end=None):
    """(debits, credits) for one account from Posted+Reversed entries,
    optionally bounded by entry_date."""
    q = db.session.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry).filter(
        JournalLine.account_id == account_id,
        JournalEntry.status.in_(["Posted", "Reversed"]),
    )
    if start:
        q = q.filter(JournalEntry.entry_date >= start)
    if end:
        q = q.filter(JournalEntry.entry_date <= end)
    debits, credits = q.one()
    return float(debits), float(credits)


def trial_balance(as_of=None):
    """Every account with activity, its net balance placed in a Debit or
    Credit column by raw sign (not natural side - that's the whole point of
    a trial balance). Totals of the two columns must be equal; if they
    aren't, the ledger itself is broken."""
    rows = []
    total_debit = total_credit = 0.0
    for acct in Account.query.order_by(Account.code.asc()).all():
        debits, credits = _posted_line_sums(acct.id, end=as_of)
        if debits == 0 and credits == 0:
            continue
        net = round(debits - credits, 2)
        row = {"account": acct, "debit": net if net > 0 else 0.0, "credit": -net if net < 0 else 0.0}
        total_debit += row["debit"]
        total_credit += row["credit"]
        rows.append(row)
    return {
        "rows": rows,
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "balanced": abs(total_debit - total_credit) < 0.01,
        "as_of": as_of,
    }


def income_statement(start=None, end=None):
    """P&L for a date range: Income minus Expenses, natural-sign amounts."""
    income_rows, expense_rows = [], []
    total_income = total_expense = 0.0
    for acct in Account.query.filter(Account.account_type.in_(["Income", "Expense"])).order_by(Account.code.asc()).all():
        debits, credits = _posted_line_sums(acct.id, start=start, end=end)
        if debits == 0 and credits == 0:
            continue
        if acct.account_type == "Income":
            amount = round(credits - debits, 2)   # credit-normal
            income_rows.append({"account": acct, "amount": amount})
            total_income += amount
        else:
            amount = round(debits - credits, 2)   # debit-normal
            expense_rows.append({"account": acct, "amount": amount})
            total_expense += amount
    return {
        "income_rows": income_rows, "expense_rows": expense_rows,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "net_income": round(total_income - total_expense, 2),
        "start": start, "end": end,
    }


def balance_sheet(as_of=None):
    """Assets = Liabilities + Equity, where Equity includes a computed
    "Current Earnings" line (all income minus all expenses up to the date).
    There is no period-closing in this system, so earnings are always
    carried as this computed line rather than a closed-out retained
    earnings account. If the check fails, the ledger is broken - the report
    says so loudly instead of hiding it."""
    sections = {"Asset": [], "Liability": [], "Equity": []}
    totals = {"Asset": 0.0, "Liability": 0.0, "Equity": 0.0}
    for acct in Account.query.filter(Account.account_type.in_(["Asset", "Liability", "Equity"])).order_by(Account.code.asc()).all():
        debits, credits = _posted_line_sums(acct.id, end=as_of)
        if debits == 0 and credits == 0:
            continue
        amount = round(debits - credits, 2) if acct.account_type == "Asset" else round(credits - debits, 2)
        sections[acct.account_type].append({"account": acct, "amount": amount})
        totals[acct.account_type] += amount

    pl = income_statement(end=as_of)
    current_earnings = pl["net_income"]
    total_equity_with_earnings = round(totals["Equity"] + current_earnings, 2)
    total_liab_equity = round(totals["Liability"] + total_equity_with_earnings, 2)
    return {
        "sections": sections,
        "totals": {k: round(v, 2) for k, v in totals.items()},
        "current_earnings": current_earnings,
        "total_equity_with_earnings": total_equity_with_earnings,
        "total_liab_equity": total_liab_equity,
        "total_assets": round(totals["Asset"], 2),
        "balanced": abs(totals["Asset"] - total_liab_equity) < 0.01,
        "as_of": as_of,
    }


def has_opening_balances():
    return JournalEntry.query.filter_by(source_module=OPENING_BALANCE_SOURCE).filter(
        JournalEntry.status.in_(["Posted", "Reversed"])
    ).count() > 0


def create_opening_balances(as_of_date, balances, created_by_id=None):
    """balances: list of {account_id, amount} where amount is on the
    account's NATURAL side (positive Cash = debit; positive Loan = credit;
    negative flips). The plug difference goes to Opening Balance Equity
    (3100) so the entry always balances. Posted immediately."""
    obe = Account.query.filter_by(code="3100").first()
    if not obe:
        raise ValueError("Opening Balance Equity account (3100) not found.")

    lines = []
    net_debit = 0.0
    for item in balances:
        amount = round(float(item.get("amount") or 0), 2)
        if amount == 0:
            continue
        acct = db.session.get(Account, int(item["account_id"]))
        if not acct:
            raise ValueError("Account not found in opening balances.")
        if acct.id == obe.id:
            raise ValueError("Opening Balance Equity is computed automatically - don't enter it directly.")
        # positive on natural side; negative flips to the other side
        side_debit = (acct.normal_side == "debit") == (amount > 0)
        value = abs(amount)
        lines.append({
            "account_id": acct.id,
            "debit": value if side_debit else 0,
            "credit": 0 if side_debit else value,
            "description": "Opening balance",
        })
        net_debit += value if side_debit else -value

    if not lines:
        raise ValueError("Enter at least one non-zero opening balance.")

    plug = round(net_debit, 2)
    if abs(plug) >= 0.01:
        lines.append({
            "account_id": obe.id,
            "debit": 0 if plug > 0 else abs(plug),
            "credit": plug if plug > 0 else 0,
            "description": "Opening balance equity (balancing line)",
        })

    return create_journal_entry(
        entry_date=as_of_date,
        lines=lines,
        memo=f"Opening balances as of {as_of_date}",
        source_module=OPENING_BALANCE_SOURCE,
        created_by_id=created_by_id, post=True, posted_by_id=created_by_id,
    )
