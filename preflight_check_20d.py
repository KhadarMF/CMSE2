"""Phase 20D pre-flight check. Run this BEFORE `flask db upgrade` on production.

    python preflight_check_20d.py

It changes nothing. It answers three questions:

  1. Is SECRET_KEY set to something the app will accept? (If not, the app
     will refuse to boot after this deploy - better to find out now.)
  2. Are there any stored money values with more than 2 decimal places?
     Converting FLOAT -> NUMERIC(14,2) rounds them, so you should see the
     list first and confirm the rounding is acceptable.
  3. Is the current schema what the migration expects?
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

try:
    import sqlalchemy as sa
except ImportError:
    sys.exit("sqlalchemy is not installed. Run: pip install -r requirements.txt")


MONEY_COLUMNS = [
    ("material_item", "unit_cost", 2),
    ("quotation_item", "unit_price", 2),
    ("journal_entry", "original_amount", 2),
    ("journal_entry", "exchange_rate", 6),
    ("employee_project_payroll", "work_days", 3),
    ("employee_project_payroll", "salary_amount", 2),
    ("employee_project_payroll", "allowance_amount", 2),
    ("employee_project_payroll", "deduction_amount", 2),
    ("employee_project_payroll", "previous_balance", 2),
    ("journal_line", "debit", 2),
    ("journal_line", "credit", 2),
    ("material_request_line", "quantity_requested", 3),
    ("material_request_line", "estimated_unit_cost", 2),
    ("material_return_line", "quantity_returned", 3),
    ("material_return_line", "unit_cost", 2),
    ("payment_request", "amount", 2),
    ("payroll_payment", "amount", 2),
    ("project_payroll_entry", "work_days", 3),
    ("project_payroll_entry", "project_amount", 2),
    ("project_payroll_entry", "allowance_amount", 2),
    ("project_payroll_entry", "deduction_amount", 2),
    ("project_payroll_entry", "previous_balance", 2),
    ("sales_quotation_line", "quantity", 3),
    ("sales_quotation_line", "unit_price", 2),
    ("material_issue_line", "quantity_issued", 3),
    ("material_issue_line", "unit_cost", 2),
    ("payment_request_payment", "amount", 2),
    ("project_payroll_payment", "amount", 2),
]

UNSAFE_KEYS = {"", "change-this-secret-key",
               "change-this-to-a-long-random-secret-key", "secret", "dev"}


def line(char="-"):
    print(char * 72)


def check_secret_key():
    line("=")
    print("1. SECRET_KEY")
    line()
    key = (os.environ.get("SECRET_KEY") or "").strip()
    if key.lower() in UNSAFE_KEYS:
        print("   FAIL: missing or still the placeholder value.")
        print("   The app will refuse to start after this deploy.")
        print("   Generate one now:")
        print('     python -c "import secrets; print(secrets.token_hex(32))"')
        return False
    if len(key) < 32:
        print(f"   FAIL: only {len(key)} characters; 32 are required.")
        return False
    print(f"   OK: {len(key)} characters.")
    return True


def check_precision(engine):
    line("=")
    print("2. Stored values with more decimals than the new columns keep")
    line()
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    problems = 0

    with engine.connect() as conn:
        for table, column, scale in MONEY_COLUMNS:
            if table not in tables:
                continue
            if column not in [c["name"] for c in inspector.get_columns(table)]:
                continue
            try:
                sql = sa.text(
                    f'SELECT count(*) FROM "{table}" '
                    f'WHERE "{column}" IS NOT NULL '
                    f'AND round(CAST("{column}" AS numeric), {scale}) '
                    f'  <> CAST("{column}" AS numeric)'
                )
                count = conn.execute(sql).scalar() or 0
            except Exception:
                # SQLite has no numeric cast; fall back to a Python check.
                try:
                    rows = conn.execute(
                        sa.text(f'SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL')
                    ).scalars().all()
                    count = sum(1 for v in rows if round(float(v), scale) != float(v))
                except Exception:
                    continue
            if count:
                problems += count
                print(f"   {table}.{column}: {count} row(s) will be rounded to {scale} dp")

    if problems == 0:
        print("   OK: nothing will be rounded.")
    else:
        print()
        print(f"   {problems} value(s) will change. Review them, then proceed.")
        print("   This is normally correct - money should not carry 3+ decimals -")
        print("   but confirm with the Finance Officer before running the upgrade.")
    return problems


def check_schema(engine):
    line("=")
    print("3. Current schema state")
    line()
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    print(f"   tables found: {len(tables)}")
    stamped = "alembic_version" in tables
    print(f"   alembic_version present: {stamped}")
    if not stamped:
        print()
        print("   This database has never been managed by Alembic. Run:")
        print("     flask db stamp cc82184d6822")
        print("     flask db upgrade")
    else:
        with engine.connect() as conn:
            rev = conn.execute(sa.text("select version_num from alembic_version")).scalar()
        print(f"   current revision: {rev}")
        print("   Run: flask db upgrade")

    floats = [
        f"{t}.{c}"
        for t, c, _ in MONEY_COLUMNS
        if t in tables
        for col in inspector.get_columns(t)
        if col["name"] == c and isinstance(col["type"], sa.Float)
    ]
    print(f"   money columns still FLOAT: {len(floats)}")


def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        sys.exit("DATABASE_URL is not set.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    print()
    print("Cadceed-Maal ERP - Phase 20D pre-flight check")
    print(f"database: {url.split('@')[-1]}")
    print()

    key_ok = check_secret_key()

    engine = sa.create_engine(url)
    check_precision(engine)
    check_schema(engine)

    line("=")
    print()
    if not key_ok:
        print("STOP: fix SECRET_KEY before deploying.")
        sys.exit(1)
    print("Reminder: take a backup and DOWNLOAD IT OFF THE SERVER first.")
    print("Render's disk is ephemeral - a backup left on it is not a backup.")
    print()


if __name__ == "__main__":
    main()
