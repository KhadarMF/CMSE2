from sqlalchemy import text
from app import db


def sync_postgres_sequences():
    """Reset PostgreSQL serial/identity sequences to MAX(id) for all tables.

    This prevents 500 errors like duplicate key value violates unique constraint
    after importing/restoring data where table IDs are ahead of their sequences.
    Safe to call on startup; it is a no-op for SQLite/local testing.
    """
    try:
        engine_name = db.engine.name
    except Exception:
        return
    if engine_name != "postgresql":
        return
    try:
        inspector = db.inspect(db.engine)
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            if not any(c.get("name") == "id" for c in columns):
                continue
            seq_sql = text("SELECT pg_get_serial_sequence(:table_name, 'id')")
            sequence_name = db.session.execute(seq_sql, {"table_name": table_name}).scalar()
            if not sequence_name:
                continue
            set_sql = text(
                f"SELECT setval(:sequence_name, COALESCE((SELECT MAX(id) FROM \"{table_name}\"), 1), true)"
            )
            db.session.execute(set_sql, {"sequence_name": sequence_name})
        db.session.commit()
    except Exception:
        db.session.rollback()


def warn_if_migrations_pending(app):
    """Log loudly when the database schema is behind the code.

    Before Phase 20D the app "fixed" schema drift by calling db.create_all()
    on every request. That created missing tables but never missing columns,
    so a model change could deploy cleanly and then throw UndefinedColumn at
    a user hours later. Now the mismatch is reported at boot instead.
    """
    try:
        from alembic.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from flask_migrate import current as _unused  # noqa: F401  (ensures ext is loaded)
        from flask import current_app
        from app import db

        directory = current_app.extensions["migrate"].directory
        script = ScriptDirectory(directory)
        head = script.get_current_head()

        with db.engine.connect() as connection:
            context = MigrationContext.configure(connection)
            db_rev = context.get_current_revision()

        if db_rev is None:
            app.logger.warning(
                "SCHEMA: this database has never been stamped by Alembic. "
                "Run `flask db stamp <baseline>` (existing DB) or "
                "`flask db upgrade` (new DB) before using the app."
            )
        elif db_rev != head:
            app.logger.warning(
                "SCHEMA MISMATCH: database is at revision %s but the code "
                "expects %s. Run `flask db upgrade`.", db_rev, head
            )
        else:
            app.logger.info("SCHEMA: up to date (revision %s).", db_rev)
    except Exception as exc:  # pragma: no cover - never block boot on this
        app.logger.info("Schema version check skipped: %s", exc)
