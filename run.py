"""Local development launcher.

`python run.py` is intentionally a one-command first-run experience.  It
creates a git-ignored local `.env` with a unique secret, backs up a recognized
legacy SQLite database, and applies migrations. WSGI/Render imports do not
execute this convenience setup and still require production environment
variables.
"""

import os
from pathlib import Path
import re
import secrets


from app.local_setup import PROJECT_ROOT, prepare_local_environment


if __name__ == "__main__":
    prepare_local_environment()

from app import create_app, db

app = create_app()


def _backup_sqlite_database(database_path):
    """Take a consistent SQLite backup before first-time legacy stamping."""
    from datetime import datetime
    import sqlite3

    source_path = Path(database_path).resolve()
    backup_dir = PROJECT_ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / (
        f"local_auto_before_phase20h_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    with sqlite3.connect(str(source_path)) as source:
        with sqlite3.connect(str(backup_path)) as destination:
            source.backup(destination)
    return backup_path


def upgrade_local_sqlite_database():
    """Upgrade new, managed, or confidently recognized legacy SQLite DBs."""
    import sqlalchemy as sa
    from flask_migrate import stamp, upgrade

    with app.app_context():
        if db.engine.url.get_backend_name() != "sqlite":
            print("DATABASE SETUP: PostgreSQL detected; run `flask db upgrade` explicitly.")
            return
        inspector = sa.inspect(db.engine)
        tables = set(inspector.get_table_names())
        if not tables or "alembic_version" in tables:
            upgrade()
            print("DATABASE SETUP: SQLite schema is up to date.")
            return True

        # Phase 20D's documented onboarding for a pre-Alembic installation is
        # "backup -> stamp the full-schema baseline -> upgrade". Automate that
        # only when this is clearly a mature CMSE database, never for an
        # arbitrary or partial SQLite file.
        required_tables = {
            "user", "project", "employee", "team",
            "daily_site_report", "payment_request",
        }
        if len(tables) >= 40 and required_tables.issubset(tables):
            backup_path = _backup_sqlite_database(db.engine.url.database)
            print(f"DATABASE BACKUP: {backup_path}")
            stamp(revision="cc82184d6822")
            upgrade()
            print("DATABASE SETUP: legacy SQLite schema upgraded to the current release.")
            return True
        else:
            raise RuntimeError(
                "DATABASE SETUP STOPPED: this unstamped SQLite file is not a "
                "recognized full CMSE database, so it was not modified."
            )


if __name__ == "__main__":
    if upgrade_local_sqlite_database():
        from init_db import initialize_database
        initialize_database(app)
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
