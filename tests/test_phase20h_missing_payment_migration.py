"""Regression test for legacy databases missing payment request tables."""

import sqlalchemy as sa


def test_upgrade_repairs_missing_payment_request_tables(app):
    from app import db
    from flask_migrate import upgrade

    # Reproduce the production drift: Alembic says Phase 20H is installed,
    # while the pre-Alembic database never had these two tables.
    with db.engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE payment_request_payment"))
        connection.execute(sa.text("DROP TABLE payment_request"))
        connection.execute(
            sa.text(
                "UPDATE alembic_version SET version_num = 'b20h0000a001'"
            )
        )

    upgrade()

    inspector = sa.inspect(db.engine)
    assert "payment_request" in inspector.get_table_names()
    assert "payment_request_payment" in inspector.get_table_names()

    payment_columns = {
        column["name"] for column in inspector.get_columns("payment_request")
    }
    assert {
        "requested_by_id",
        "project_id",
        "team_id",
        "request_type",
        "amount",
        "status",
    }.issubset(payment_columns)

    current_revision = db.session.execute(
        sa.text("SELECT version_num FROM alembic_version")
    ).scalar_one()
    from alembic.script import ScriptDirectory
    assert current_revision == ScriptDirectory("migrations").get_current_head()
