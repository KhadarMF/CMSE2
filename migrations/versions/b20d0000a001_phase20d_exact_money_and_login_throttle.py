"""Phase 20D: exact money columns + login throttle table

Existing deployments were created before Alembic existed. Their tables were
built by db.create_all(), so every money column is a FLOAT (Postgres: double
precision) and the login_attempt table is absent.

This migration brings such a database up to what the models now declare:

  * 21 money columns  FLOAT -> NUMERIC(14,2)
  *  6 quantity cols  FLOAT -> NUMERIC(14,3)
  *  1 exchange rate  FLOAT -> NUMERIC(18,6)
  *  creates login_attempt

Every step checks the live schema first, so it is safe to run against a
database that already happens to be correct (for example one created fresh
from the baseline migration).

BEFORE RUNNING THIS ON PRODUCTION: take a backup and download it off the
server. Numeric conversion rewrites the money columns in place.

Revision ID: b20d0000a001
Revises: cc82184d6822
"""
from alembic import op
import sqlalchemy as sa


revision = "b20d0000a001"
down_revision = "cc82184d6822"
branch_labels = None
depends_on = None


MONEY = sa.Numeric(14, 2)
QUANTITY = sa.Numeric(14, 3)
RATE = sa.Numeric(18, 6)

# (table, column, target type)
COLUMNS = [
    ("material_item", "unit_cost", MONEY),
    ("quotation_item", "unit_price", MONEY),
    ("journal_entry", "exchange_rate", RATE),
    ("journal_entry", "original_amount", MONEY),
    ("employee_project_payroll", "work_days", QUANTITY),
    ("employee_project_payroll", "salary_amount", MONEY),
    ("employee_project_payroll", "allowance_amount", MONEY),
    ("employee_project_payroll", "deduction_amount", MONEY),
    ("employee_project_payroll", "previous_balance", MONEY),
    ("journal_line", "debit", MONEY),
    ("journal_line", "credit", MONEY),
    ("material_request_line", "quantity_requested", QUANTITY),
    ("material_request_line", "estimated_unit_cost", MONEY),
    ("material_return_line", "quantity_returned", QUANTITY),
    ("material_return_line", "unit_cost", MONEY),
    ("payment_request", "amount", MONEY),
    ("payroll_payment", "amount", MONEY),
    ("project_payroll_entry", "work_days", QUANTITY),
    ("project_payroll_entry", "project_amount", MONEY),
    ("project_payroll_entry", "allowance_amount", MONEY),
    ("project_payroll_entry", "deduction_amount", MONEY),
    ("project_payroll_entry", "previous_balance", MONEY),
    ("sales_quotation_line", "quantity", QUANTITY),
    ("sales_quotation_line", "unit_price", MONEY),
    ("material_issue_line", "quantity_issued", QUANTITY),
    ("material_issue_line", "unit_cost", MONEY),
    ("payment_request_payment", "amount", MONEY),
    ("project_payroll_payment", "amount", MONEY),
]


def _inspector():
    return sa.inspect(op.get_bind())


def _column(inspector, table, column):
    if table not in inspector.get_table_names():
        return None
    for col in inspector.get_columns(table):
        if col["name"] == column:
            return col
    return None


def _is_already_numeric(col):
    return isinstance(col["type"], sa.Numeric) and not isinstance(col["type"], sa.Float)


def upgrade():
    bind = op.get_bind()
    inspector = _inspector()
    dialect = bind.dialect.name

    # --- login_attempt -----------------------------------------------------
    if "login_attempt" not in inspector.get_table_names():
        op.create_table(
            "login_attempt",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("attempted_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_login_attempt_email", "login_attempt", ["email"])
        op.create_index("ix_login_attempt_ip_address", "login_attempt", ["ip_address"])
        op.create_index("ix_login_attempt_attempted_at", "login_attempt", ["attempted_at"])
        op.create_index("ix_login_attempt_email_time", "login_attempt", ["email", "attempted_at"])
        op.create_index("ix_login_attempt_ip_time", "login_attempt", ["ip_address", "attempted_at"])

    # --- money / quantity / rate columns -----------------------------------
    for table, column, target in COLUMNS:
        existing = _column(inspector, table, column)
        if existing is None:
            # Table or column absent on this deployment - nothing to convert.
            continue
        if _is_already_numeric(existing):
            continue

        if dialect == "postgresql":
            # USING is required: Postgres will not implicitly cast double
            # precision to numeric on ALTER TYPE.
            op.alter_column(
                table, column,
                type_=target,
                existing_nullable=existing.get("nullable", True),
                postgresql_using=f'"{column}"::numeric',
            )
        else:
            # SQLite cannot ALTER a column type; batch mode rebuilds the
            # table, copies the rows and swaps it in.
            with op.batch_alter_table(table) as batch:
                batch.alter_column(
                    column,
                    type_=target,
                    existing_nullable=existing.get("nullable", True),
                )


def downgrade():
    bind = op.get_bind()
    inspector = _inspector()
    dialect = bind.dialect.name

    for table, column, _target in COLUMNS:
        existing = _column(inspector, table, column)
        if existing is None or not _is_already_numeric(existing):
            continue
        if dialect == "postgresql":
            op.alter_column(
                table, column,
                type_=sa.Float(),
                existing_nullable=existing.get("nullable", True),
                postgresql_using=f'"{column}"::double precision',
            )
        else:
            with op.batch_alter_table(table) as batch:
                batch.alter_column(
                    column,
                    type_=sa.Float(),
                    existing_nullable=existing.get("nullable", True),
                )

    if "login_attempt" in _inspector().get_table_names():
        op.drop_table("login_attempt")
