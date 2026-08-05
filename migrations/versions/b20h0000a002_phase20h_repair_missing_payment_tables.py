"""Phase 20H repair: create payment request tables when legacy DB lacks them.

Revision ID: b20h0000a002
Revises: b20h0000a001

Some long-running installations were stamped at the Phase 20D baseline even
though their pre-Alembic schema did not contain ``payment_request``.  The
Phase 20G and 20H bridge migrations deliberately skipped an absent table, so
those installations later failed when a project page queried payment
requests.  This additive repair creates only the missing tables and never
changes or deletes an existing payment request record.
"""

from alembic import op
import sqlalchemy as sa


revision = "b20h0000a002"
down_revision = "b20h0000a001"
branch_labels = None
depends_on = None


MONEY = sa.Numeric(14, 2)


def _table_exists(table_name):
    return table_name in set(sa.inspect(op.get_bind()).get_table_names())


def _create_payment_request():
    if _table_exists("payment_request"):
        return

    op.create_table(
        "payment_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_no", sa.String(length=120), nullable=True),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("material_request_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("request_type", sa.String(length=100), nullable=True),
        sa.Column("payee_name", sa.String(length=180), nullable=False),
        sa.Column("payee_phone", sa.String(length=80), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("needed_by_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=True),
        sa.Column("manager_approved_by_id", sa.Integer(), nullable=True),
        sa.Column("manager_approved_at", sa.DateTime(), nullable=True),
        sa.Column("manager_comment", sa.Text(), nullable=True),
        sa.Column("finance_approved_by_id", sa.Integer(), nullable=True),
        sa.Column("finance_approved_at", sa.DateTime(), nullable=True),
        sa.Column("finance_comment", sa.Text(), nullable=True),
        sa.Column("rejected_by_id", sa.Integer(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("rejected_at_stage", sa.String(length=80), nullable=True),
        sa.Column("cancelled_by_id", sa.Integer(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("attachment_original_name", sa.String(length=255), nullable=True),
        sa.Column("attachment_stored_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["user.id"],
            name="fk_payment_request_requested_by_id_user",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branch.id"],
            name="fk_payment_request_branch_id_branch",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["department.id"],
            name="fk_payment_request_department_id_department",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"],
            name="fk_payment_request_project_id_project",
        ),
        sa.ForeignKeyConstraint(
            ["material_request_id"], ["material_request.id"],
            name="fk_payment_request_material_request_id_material_request",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["team.id"],
            name="fk_payment_request_team_id_team",
        ),
        sa.ForeignKeyConstraint(
            ["manager_approved_by_id"], ["user.id"],
            name="fk_payment_request_manager_approved_by_id_user",
        ),
        sa.ForeignKeyConstraint(
            ["finance_approved_by_id"], ["user.id"],
            name="fk_payment_request_finance_approved_by_id_user",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_id"], ["user.id"],
            name="fk_payment_request_rejected_by_id_user",
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_id"], ["user.id"],
            name="fk_payment_request_cancelled_by_id_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_no", name="uq_payment_request_request_no"),
    )


def _create_payment_request_payment():
    if _table_exists("payment_request_payment"):
        return

    op.create_table(
        "payment_request_payment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_request_id", sa.Integer(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("payment_method", sa.String(length=80), nullable=True),
        sa.Column("reference_no", sa.String(length=150), nullable=True),
        sa.Column("payee_phone", sa.String(length=80), nullable=True),
        sa.Column("proof_original_name", sa.String(length=255), nullable=True),
        sa.Column("proof_stored_name", sa.String(length=255), nullable=True),
        sa.Column("paid_by_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["payment_request_id"], ["payment_request.id"],
            name="fk_payment_request_payment_payment_request_id_payment_request",
        ),
        sa.ForeignKeyConstraint(
            ["paid_by_id"], ["user.id"],
            name="fk_payment_request_payment_paid_by_id_user",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def upgrade():
    _create_payment_request()
    _create_payment_request_payment()


def downgrade():
    raise RuntimeError(
        "This repair may have created production payment tables. Restore a "
        "pre-upgrade backup instead of dropping them automatically."
    )
