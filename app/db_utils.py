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
