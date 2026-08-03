from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.models import (
    Account, JournalEntry, JournalLine, AccountMapping,
    ACCOUNT_TYPES, PAYMENT_REQUEST_CATEGORIES, PROJECT_PAYMENT_METHODS,
)
from app.accounting_service import (
    ensure_default_accounts, create_journal_entry, post_entry, create_reversal,
    account_balance, get_slsh_rate, SLSH_RATE_SETTING_KEY,
)
from app.settings import get_setting, set_setting

accounting_bp = Blueprint("accounting", __name__, url_prefix="/accounting")

# Same two role tiers as payments/payroll. Viewing is governed by the
# form-permission grant (permission_enforcer); posting/reversing/mapping
# changes additionally require a finance-tier role.
FINANCE_ROLES = ["Admin", "Management", "Finance Officer"]


def can_post():
    return current_user.role in FINANCE_ROLES


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None


@accounting_bp.before_app_request
def ensure_accounting_tables():
    # Same lazy-create convention as the other modules, plus one-time
    # seeding of the default chart of accounts and mappings.
    # Phase 20D: db.create_all() removed - Alembic owns the schema now.
    # Seeding the default chart of accounts is DATA, not schema, so it stays.
    try:
        ensure_default_accounts()
    except Exception:
        db.session.rollback()


@accounting_bp.route("/")
@login_required
def dashboard():
    accounts = Account.query.filter_by(is_active=True).order_by(Account.code.asc()).all()
    type_totals = {t: 0.0 for t in ACCOUNT_TYPES}
    balances = {}
    for a in accounts:
        b = account_balance(a.id)
        balances[a.id] = b
        type_totals[a.account_type] = type_totals.get(a.account_type, 0.0) + b
    recent = JournalEntry.query.order_by(JournalEntry.created_at.desc()).limit(10).all()
    draft_count = JournalEntry.query.filter_by(status="Draft").count()
    cash_codes = ("1000", "1010", "1020", "1030")
    cash_accounts = [a for a in accounts if a.code in cash_codes]
    return render_template(
        "accounting/dashboard.html",
        type_totals=type_totals, recent=recent, draft_count=draft_count,
        cash_accounts=cash_accounts, balances=balances,
        slsh_rate=get_slsh_rate(), can_post=can_post(),
    )


# ------------------------- Chart of Accounts -------------------------

@accounting_bp.route("/accounts")
@login_required
def accounts():
    all_accounts = Account.query.order_by(Account.code.asc()).all()
    balances = {a.id: account_balance(a.id) for a in all_accounts}
    grouped = {t: [a for a in all_accounts if a.account_type == t] for t in ACCOUNT_TYPES}
    return render_template("accounting/accounts.html", grouped=grouped, balances=balances, can_post=can_post())


@accounting_bp.route("/accounts/create", methods=["GET", "POST"])
@login_required
def create_account():
    if not can_post():
        flash("Only Admin, Management or Finance Officer can manage accounts.", "danger")
        return redirect(url_for("accounting.accounts"))
    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        name = (request.form.get("name") or "").strip()
        acc_type = request.form.get("account_type")
        if not code or not name or acc_type not in ACCOUNT_TYPES:
            flash("Code, name and a valid account type are required.", "danger")
            return redirect(url_for("accounting.create_account"))
        if Account.query.filter_by(code=code).first():
            flash(f"Account code {code} already exists.", "danger")
            return redirect(url_for("accounting.create_account"))
        parent_id = request.form.get("parent_id")
        acct = Account(
            code=code, name=name, account_type=acc_type,
            parent_id=int(parent_id) if parent_id else None,
            description=request.form.get("description"),
        )
        db.session.add(acct)
        db.session.commit()
        flash(f"Account {code} {name} created.", "success")
        return redirect(url_for("accounting.accounts"))
    return render_template(
        "accounting/account_form.html", account=None, account_types=ACCOUNT_TYPES,
        parents=Account.query.filter_by(is_active=True).order_by(Account.code.asc()).all(),
    )


@accounting_bp.route("/accounts/<int:account_id>/edit", methods=["GET", "POST"])
@login_required
def edit_account(account_id):
    if not can_post():
        flash("Only Admin, Management or Finance Officer can manage accounts.", "danger")
        return redirect(url_for("accounting.accounts"))
    acct = Account.query.get_or_404(account_id)
    has_lines = JournalLine.query.filter_by(account_id=acct.id).first() is not None
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "danger")
            return redirect(url_for("accounting.edit_account", account_id=acct.id))
        acct.name = name
        acct.description = request.form.get("description")
        # Code and type are locked once the account has journal lines -
        # changing them would silently rewrite history in every report.
        if not has_lines:
            new_code = (request.form.get("code") or "").strip()
            new_type = request.form.get("account_type")
            if new_code and new_code != acct.code:
                if Account.query.filter_by(code=new_code).first():
                    flash(f"Account code {new_code} already exists.", "danger")
                    return redirect(url_for("accounting.edit_account", account_id=acct.id))
                acct.code = new_code
            if new_type in ACCOUNT_TYPES:
                acct.account_type = new_type
        if not acct.is_system:
            acct.is_active = request.form.get("is_active") == "on"
        db.session.commit()
        flash("Account updated.", "success")
        return redirect(url_for("accounting.accounts"))
    return render_template(
        "accounting/account_form.html", account=acct, account_types=ACCOUNT_TYPES, has_lines=has_lines,
        parents=Account.query.filter(Account.id != acct.id, Account.is_active == True).order_by(Account.code.asc()).all(),
    )


@accounting_bp.route("/ledger/<int:account_id>")
@login_required
def ledger(account_id):
    acct = Account.query.get_or_404(account_id)
    lines = (
        JournalLine.query.join(JournalEntry)
        .filter(JournalLine.account_id == acct.id, JournalEntry.status.in_(["Posted", "Reversed"]))
        .order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc(), JournalLine.line_order.asc())
        .all()
    )
    running = 0.0
    rows = []
    for l in lines:
        net = float(l.debit or 0) - float(l.credit or 0)
        if acct.normal_side == "credit":
            net = -net
        running += net
        rows.append({"line": l, "entry": l.journal_entry, "running": round(running, 2)})
    return render_template("accounting/ledger.html", account=acct, rows=rows, balance=round(running, 2))


# ------------------------------ Journal ------------------------------

@accounting_bp.route("/journal")
@login_required
def journal():
    status = request.args.get("status")
    source = request.args.get("source")
    q = JournalEntry.query
    if status:
        q = q.filter_by(status=status)
    if source == "manual":
        q = q.filter(JournalEntry.source_module.is_(None))
    elif source:
        q = q.filter_by(source_module=source)
    entries = q.order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc()).limit(300).all()
    return render_template("accounting/journal_list.html", entries=entries, filters=request.args, can_post=can_post())


@accounting_bp.route("/journal/<int:entry_id>")
@login_required
def journal_detail(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    return render_template("accounting/journal_detail.html", entry=entry, can_post=can_post())


@accounting_bp.route("/journal/create", methods=["GET", "POST"])
@login_required
def create_journal():
    if not can_post():
        flash("Only Admin, Management or Finance Officer can create journal entries.", "danger")
        return redirect(url_for("accounting.journal"))
    if request.method == "POST":
        account_ids = request.form.getlist("line_account_id")
        debits = request.form.getlist("line_debit")
        credits = request.form.getlist("line_credit")
        descriptions = request.form.getlist("line_description")
        lines = []
        for i in range(len(account_ids)):
            if not account_ids[i]:
                continue
            lines.append({
                "account_id": account_ids[i],
                "debit": debits[i] if i < len(debits) else 0,
                "credit": credits[i] if i < len(credits) else 0,
                "description": descriptions[i] if i < len(descriptions) else "",
            })
        action = request.form.get("action", "post")
        try:
            entry = create_journal_entry(
                entry_date=parse_date(request.form.get("entry_date")) or date.today(),
                lines=lines,
                memo=request.form.get("memo"),
                reference=request.form.get("reference"),
                created_by_id=current_user.id,
                post=(action == "post"),
                posted_by_id=current_user.id,
            )
            db.session.commit()
            flash(f"Journal entry {entry.entry_no} {'posted' if action == 'post' else 'saved as draft'}.", "success")
            return redirect(url_for("accounting.journal_detail", entry_id=entry.id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("accounting.create_journal"))
    return render_template(
        "accounting/journal_form.html",
        accounts=Account.query.filter_by(is_active=True).order_by(Account.code.asc()).all(),
        today=date.today().isoformat(),
    )


@accounting_bp.route("/journal/<int:entry_id>/post", methods=["POST"])
@login_required
def post_journal(entry_id):
    if not can_post():
        flash("Only Admin, Management or Finance Officer can post journal entries.", "danger")
        return redirect(url_for("accounting.journal_detail", entry_id=entry_id))
    entry = JournalEntry.query.get_or_404(entry_id)
    try:
        post_entry(entry, posted_by_id=current_user.id)
        db.session.commit()
        flash(f"{entry.entry_no} posted.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("accounting.journal_detail", entry_id=entry_id))


@accounting_bp.route("/journal/<int:entry_id>/reverse", methods=["POST"])
@login_required
def reverse_journal(entry_id):
    if not can_post():
        flash("Only Admin, Management or Finance Officer can reverse journal entries.", "danger")
        return redirect(url_for("accounting.journal_detail", entry_id=entry_id))
    entry = JournalEntry.query.get_or_404(entry_id)
    try:
        reversal = create_reversal(entry, request.form.get("reason") or "", created_by_id=current_user.id)
        db.session.commit()
        flash(f"{entry.entry_no} reversed by {reversal.entry_no}.", "success")
        return redirect(url_for("accounting.journal_detail", entry_id=reversal.id))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("accounting.journal_detail", entry_id=entry_id))


@accounting_bp.route("/journal/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_journal(entry_id):
    if not can_post():
        flash("Only Admin, Management or Finance Officer can delete draft entries.", "danger")
        return redirect(url_for("accounting.journal_detail", entry_id=entry_id))
    entry = JournalEntry.query.get_or_404(entry_id)
    if entry.status != "Draft":
        # The immutability rule: posted history is never deleted.
        flash("Only Draft entries can be deleted. Posted entries must be reversed instead.", "danger")
        return redirect(url_for("accounting.journal_detail", entry_id=entry_id))
    no = entry.entry_no
    db.session.delete(entry)
    db.session.commit()
    flash(f"Draft {no} deleted.", "success")
    return redirect(url_for("accounting.journal"))


# ------------------------ Mappings & Settings ------------------------

@accounting_bp.route("/mappings", methods=["GET", "POST"])
@login_required
def mappings():
    if request.method == "POST":
        if not can_post():
            flash("Only Admin, Management or Finance Officer can change mappings.", "danger")
            return redirect(url_for("accounting.mappings"))
        for key, value in request.form.items():
            if key.startswith("map__") and value:
                _, mapping_type, map_key = key.split("__", 2)
                m = AccountMapping.query.filter_by(mapping_type=mapping_type, key=map_key).first()
                if not m:
                    m = AccountMapping(mapping_type=mapping_type, key=map_key, account_id=int(value))
                    db.session.add(m)
                else:
                    m.account_id = int(value)
        slsh_rate = (request.form.get("slsh_rate") or "").strip()
        if slsh_rate:
            try:
                if float(slsh_rate) <= 0:
                    raise ValueError
                db.session.add(set_setting(SLSH_RATE_SETTING_KEY, slsh_rate))
            except ValueError:
                flash("SLSH rate must be a positive number.", "danger")
                return redirect(url_for("accounting.mappings"))
        db.session.commit()
        flash("Mappings and settings saved.", "success")
        return redirect(url_for("accounting.mappings"))

    all_mappings = AccountMapping.query.all()
    current = {(m.mapping_type, m.key): m.account_id for m in all_mappings}
    expense_accounts = Account.query.filter_by(account_type="Expense", is_active=True).order_by(Account.code.asc()).all()
    asset_accounts = Account.query.filter_by(account_type="Asset", is_active=True).order_by(Account.code.asc()).all()
    return render_template(
        "accounting/mappings.html",
        categories=PAYMENT_REQUEST_CATEGORIES, methods=PROJECT_PAYMENT_METHODS,
        current=current, expense_accounts=expense_accounts, asset_accounts=asset_accounts,
        slsh_rate=get_setting(SLSH_RATE_SETTING_KEY, ""), can_post=can_post(),
    )


# --------------------- Phase 20C: Reports + Opening Balances ---------------------

@accounting_bp.route("/reports/trial-balance")
@login_required
def trial_balance_report():
    from app.accounting_service import trial_balance
    as_of = parse_date(request.args.get("as_of"))
    return render_template("accounting/trial_balance.html", report=trial_balance(as_of=as_of),
                           as_of=request.args.get("as_of", ""))


@accounting_bp.route("/reports/income-statement")
@login_required
def income_statement_report():
    from app.accounting_service import income_statement
    start = parse_date(request.args.get("start"))
    end = parse_date(request.args.get("end"))
    return render_template("accounting/income_statement.html",
                           report=income_statement(start=start, end=end),
                           start=request.args.get("start", ""), end=request.args.get("end", ""))


@accounting_bp.route("/reports/balance-sheet")
@login_required
def balance_sheet_report():
    from app.accounting_service import balance_sheet
    as_of = parse_date(request.args.get("as_of"))
    return render_template("accounting/balance_sheet.html", report=balance_sheet(as_of=as_of),
                           as_of=request.args.get("as_of", ""))


@accounting_bp.route("/opening-balances", methods=["GET", "POST"])
@login_required
def opening_balances():
    from app.accounting_service import create_opening_balances, has_opening_balances, account_balance
    if request.method == "POST":
        if not can_post():
            flash("Only Admin, Management or Finance Officer can enter opening balances.", "danger")
            return redirect(url_for("accounting.opening_balances"))
        account_ids = request.form.getlist("ob_account_id")
        amounts = request.form.getlist("ob_amount")
        balances = []
        for i in range(len(account_ids)):
            raw = (amounts[i] if i < len(amounts) else "").strip()
            if not raw:
                continue
            try:
                amount = float(raw)
            except ValueError:
                flash(f"Invalid amount: {raw}", "danger")
                return redirect(url_for("accounting.opening_balances"))
            if amount != 0:
                balances.append({"account_id": account_ids[i], "amount": amount})
        try:
            entry = create_opening_balances(
                as_of_date=parse_date(request.form.get("as_of_date")) or date.today(),
                balances=balances, created_by_id=current_user.id,
            )
            db.session.commit()
            flash(f"Opening balances posted as {entry.entry_no}.", "success")
            return redirect(url_for("accounting.journal_detail", entry_id=entry.id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("accounting.opening_balances"))

    accounts_list = Account.query.filter(
        Account.is_active == True, Account.code != "3100",
        Account.account_type.in_(["Asset", "Liability", "Equity"]),
    ).order_by(Account.code.asc()).all()
    return render_template(
        "accounting/opening_balances.html",
        accounts=accounts_list,
        already_entered=has_opening_balances(),
        today=date.today().isoformat(),
        can_post=can_post(),
    )
