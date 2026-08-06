"""Phase 20H repair: relax obsolete required payment-request fields.

Revision ID: b20h0000a003
Revises: b20h0000a002

Old SQLite installations have three required columns that were replaced by
the current payment workflow:

* request_date  -> created_at / needed_by_date
* payment_type -> request_type / category
* created_by_id -> requested_by_id

The current model intentionally no longer writes the obsolete columns.  If
they remain NOT NULL, SQLite rejects every new request before the primary key
can be assigned.  This migration keeps the legacy columns and their data but
makes them optional.  Databases created from the current schema do not have
these columns, so the migration is a safe no-op there.
"""

from alembic import op
import sqlalchemy as sa


revision = "b20h0000a003"
down_revision = "b20h0000a002"
branch_labels = None
depends_on = None


FK_NAMING = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


LEGACY_COLUMNS = ("request_date", "payment_type", "created_by_id")


def _payment_columns():
    inspector = sa.inspect(op.get_bind())
    if "payment_request" not in set(inspector.get_table_names()):
        return {}
    return {column["name"]: column for column in inspector.get_columns(
        "payment_request"
    )}


def upgrade():
    columns = _payment_columns()
    required_legacy_columns = [
        name
        for name in LEGACY_COLUMNS
        if name in columns and columns[name].get("nullable") is False
    ]
    if not required_legacy_columns:
        return

    with op.batch_alter_table(
        "payment_request", naming_convention=FK_NAMING
    ) as batch:
        for name in required_legacy_columns:
            batch.alter_column(
                name,
                existing_type=columns[name]["type"],
                nullable=True,
            )


def downgrade():
    raise RuntimeError(
        "Legacy payment columns may contain NULL after this repair. Restore "
        "a pre-upgrade backup instead of making them required again."
    )
