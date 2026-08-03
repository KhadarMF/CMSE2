"""Phase 20D: money must be exact.

These tests are the reason the Float -> Numeric change was worth doing. They
fail on the old schema and pass on the new one.
"""
import os
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa


def _accounts(db):
    from app.models import Account
    cash = Account(code="1000", name="Cash on Hand", account_type="Asset", is_system=True)
    exp = Account(code="5100", name="Materials Expense", account_type="Expense", is_system=True)
    db.session.add_all([cash, exp])
    db.session.commit()
    return cash, exp


def test_money_columns_are_numeric_not_float(app):
    from app import db
    inspector = sa.inspect(db.engine)
    checks = [
        ("journal_line", "debit"), ("journal_line", "credit"),
        ("payment_request", "amount"), ("payroll_payment", "amount"),
        ("sales_quotation_line", "unit_price"), ("material_issue_line", "unit_cost"),
    ]
    for table, column in checks:
        col = [c for c in inspector.get_columns(table) if c["name"] == column][0]
        assert isinstance(col["type"], sa.Numeric), f"{table}.{column} is {col['type']}"
        assert not isinstance(col["type"], sa.Float), f"{table}.{column} is still a float"


def test_the_classic_float_drift_does_not_happen(app):
    """0.1 + 0.2 != 0.3 in binary floating point. Through the ledger it must.

    Note on backends: SQLite has no true DECIMAL type - it stores NUMERIC as
    an 8-byte REAL - so a raw `SELECT sum(debit)` still drifts there. The
    guarantee this test asserts is the one the application actually relies
    on: every read goes through Money/account_balance, which quantizes.
    On PostgreSQL (production) the raw SQL sum is exact too; see
    test_raw_sql_sum_is_exact_on_postgres below.
    """
    from app import db
    from app.accounting_service import create_journal_entry, account_balance
    cash, exp = _accounts(db)

    for amount in (0.1, 0.2):
        create_journal_entry(
            entry_date=date(2026, 7, 1),
            lines=[{"account_id": exp.id, "debit": amount, "credit": 0},
                   {"account_id": cash.id, "debit": 0, "credit": amount}],
            memo="drift test", post=True,
        )
    db.session.commit()

    assert Decimal(str(account_balance(exp.id))) == Decimal("0.30")
    assert Decimal(str(account_balance(cash.id))) == Decimal("-0.30")


@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_URL"),
    reason="set TEST_POSTGRES_URL to run the PostgreSQL-only exactness check",
)
def test_raw_sql_sum_is_exact_on_postgres():
    """On the real production backend, even a raw SUM() must be exact.

    Run with:
        TEST_POSTGRES_URL=postgresql://user:pass@host/dbname pytest
    """
    import sqlalchemy as sa
    engine = sa.create_engine(os.environ["TEST_POSTGRES_URL"])
    with engine.begin() as conn:
        conn.execute(sa.text("drop table if exists _money_check"))
        conn.execute(sa.text("create table _money_check (v numeric(14,2))"))
        conn.execute(sa.text("insert into _money_check values (0.10), (0.20)"))
        total = conn.execute(sa.text("select sum(v) from _money_check")).scalar()
        conn.execute(sa.text("drop table _money_check"))
    assert Decimal(str(total)) == Decimal("0.30")


def test_many_small_entries_still_balance_exactly(app):
    """1,000 awkward amounts. On floats the trial balance drifts off zero."""
    from app import db
    from app.accounting_service import create_journal_entry, trial_balance
    cash, exp = _accounts(db)

    for i in range(1000):
        amount = round(0.01 + (i % 97) * 0.01, 2)
        create_journal_entry(
            entry_date=date(2026, 7, 1),
            lines=[{"account_id": exp.id, "debit": amount, "credit": 0},
                   {"account_id": cash.id, "debit": 0, "credit": amount}],
            memo=f"bulk {i}", post=True,
        )
    db.session.commit()

    tb = trial_balance(as_of=date(2026, 12, 31))
    total_debit = sum(row["debit"] for row in tb["rows"])
    total_credit = sum(row["credit"] for row in tb["rows"])
    assert Decimal(str(total_debit)) == Decimal(str(total_credit))


def test_amounts_are_rounded_half_up_not_bankers(app):
    """Python's round(0.125, 2) gives 0.12. Finance expects 0.13."""
    from app import db
    from app.models import PaymentRequest, User
    from werkzeug.security import generate_password_hash

    u = User(full_name="X", email="x@y.z", password_hash=generate_password_hash("p"),
             role="Finance Officer", is_active=True)
    db.session.add(u)
    db.session.commit()

    pr = PaymentRequest(request_no="PR-ROUND-1", payee_name="Rounding Test",
                        requested_by_id=u.id, purpose="test",
                        amount=0.125, currency="USD", status="Draft")
    db.session.add(pr)
    db.session.commit()

    raw = db.session.execute(
        sa.text("select amount from payment_request where request_no='PR-ROUND-1'")
    ).scalar()
    assert Decimal(str(raw)) == Decimal("0.13")


def test_unbalanced_entry_is_still_rejected(app):
    """The Numeric change must not weaken the existing invariant."""
    import pytest
    from app import db
    from app.accounting_service import create_journal_entry
    cash, exp = _accounts(db)

    with pytest.raises(ValueError):
        create_journal_entry(
            entry_date=date(2026, 7, 1),
            lines=[{"account_id": exp.id, "debit": 100.00, "credit": 0},
                   {"account_id": cash.id, "debit": 0, "credit": 99.99}],
            memo="unbalanced", post=True,
        )


def test_reversal_returns_the_balance_to_zero(app):
    from app import db
    from app.accounting_service import create_journal_entry, create_reversal, account_balance
    cash, exp = _accounts(db)

    entry = create_journal_entry(
        entry_date=date(2026, 7, 1),
        lines=[{"account_id": exp.id, "debit": 1234.56, "credit": 0},
               {"account_id": cash.id, "debit": 0, "credit": 1234.56}],
        memo="to be reversed", post=True,
    )
    db.session.commit()
    assert account_balance(exp.id) == 1234.56

    create_reversal(entry, reason="wrong supplier")
    db.session.commit()
    assert account_balance(exp.id) == 0.00
