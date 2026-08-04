"""Phase 20H: Team Leader payment requests and daily reporting.

Revision ID: b20h0000a001
Revises: b20g0000a001

The migration is additive so it can run against both a clean Phase 20G
database and an older, bridged installation without deleting business data.
"""

from alembic import op
import sqlalchemy as sa


revision = "b20h0000a001"
down_revision = "b20g0000a001"
branch_labels = None
depends_on = None


FK_NAMING = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


DAILY_COLUMNS = [
    sa.Column("team_id", sa.Integer(), nullable=True),
    sa.Column("site_location", sa.String(length=200), nullable=True),
    sa.Column("weather", sa.String(length=100), nullable=True),
    sa.Column("planned_activities", sa.Text(), nullable=True),
    sa.Column("employees_present", sa.String(length=80), nullable=True),
    sa.Column("employees_absent", sa.String(length=80), nullable=True),
    sa.Column("normal_hours", sa.String(length=50), nullable=True),
    sa.Column("overtime_hours", sa.String(length=50), nullable=True),
    sa.Column("completed_quantity", sa.String(length=80), nullable=True),
    sa.Column("quantity_unit", sa.String(length=80), nullable=True),
    sa.Column("delayed_activities", sa.Text(), nullable=True),
    sa.Column("delay_reason", sa.Text(), nullable=True),
]


PAYMENT_COLUMNS = [
    sa.Column("team_id", sa.Integer(), nullable=True),
    sa.Column("request_type", sa.String(length=100), nullable=True),
]


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name):
    return table_name in set(_inspector().get_table_names())


def _column_names(table_name):
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _has_fk(table_name, column_name, referred_table):
    return any(
        fk.get("constrained_columns") == [column_name]
        and fk.get("referred_table") == referred_table
        for fk in _inspector().get_foreign_keys(table_name)
    )


def _has_daily_unique_constraint():
    wanted = {"project_id", "team_id", "report_date"}
    return any(
        set(constraint.get("column_names") or []) == wanted
        for constraint in _inspector().get_unique_constraints("daily_site_report")
    )


def _extend_payment_requests():
    if not _table_exists("payment_request"):
        return

    existing = _column_names("payment_request")
    add_team_fk = not _has_fk("payment_request", "team_id", "team")
    with op.batch_alter_table(
        "payment_request", naming_convention=FK_NAMING
    ) as batch:
        for column in PAYMENT_COLUMNS:
            if column.name not in existing:
                batch.add_column(column)
        if add_team_fk:
            batch.create_foreign_key(
                "fk_payment_request_team_id_team", "team", ["team_id"], ["id"]
            )

    op.get_bind().execute(
        sa.text(
            "UPDATE payment_request SET request_type = 'Team Expense' "
            "WHERE request_type IS NULL OR trim(request_type) = ''"
        )
    )


def _extend_daily_reports():
    if not _table_exists("daily_site_report"):
        return

    existing = _column_names("daily_site_report")
    add_team_fk = not _has_fk("daily_site_report", "team_id", "team")
    add_unique = not _has_daily_unique_constraint()
    with op.batch_alter_table(
        "daily_site_report", naming_convention=FK_NAMING
    ) as batch:
        for column in DAILY_COLUMNS:
            if column.name not in existing:
                batch.add_column(column)
        if add_team_fk:
            batch.create_foreign_key(
                "fk_daily_site_report_team_id_team", "team", ["team_id"], ["id"]
            )
        if add_unique:
            batch.create_unique_constraint(
                "uq_daily_site_report_project_team_date",
                ["project_id", "team_id", "report_date"],
            )


def upgrade():
    _extend_payment_requests()
    _extend_daily_reports()


def downgrade():
    raise RuntimeError(
        "Phase 20H adds Team Leader business records. Restore a pre-upgrade "
        "backup instead of automatically dropping those columns."
    )
