"""Regression test for required obsolete fields in legacy SQLite databases."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_repair_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "b20h0000a003_phase20h_relax_legacy_payment_fields.py"
    )
    spec = importlib.util.spec_from_file_location(
        "phase20h_legacy_payment_constraint_repair", migration_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repair_relaxes_only_obsolete_required_columns(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    metadata = sa.MetaData()
    sa.Table(
        "payment_request",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_no", sa.String(120), nullable=True),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("payment_type", sa.String(120), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
    )
    metadata.create_all(engine)

    migration = _load_repair_migration()
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        migration.op = Operations(context)
        migration.upgrade()

        columns = {
            column["name"]: column
            for column in sa.inspect(connection).get_columns("payment_request")
        }
        assert columns["request_date"]["nullable"] is True
        assert columns["payment_type"]["nullable"] is True
        assert columns["created_by_id"]["nullable"] is True
        assert columns["amount"]["nullable"] is False

        # This is the behaviour the current ORM needs: an insert may omit the
        # obsolete fields while required current fields remain enforced.
        connection.execute(
            sa.text(
                "INSERT INTO payment_request (request_no, amount) "
                "VALUES ('PR-TEST-1', 100.00)"
            )
        )

    engine.dispose()
