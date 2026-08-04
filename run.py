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


PROJECT_ROOT = Path(__file__).resolve().parent


def _set_env_value(content, key, value):
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    replacement = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(replacement, content, count=1)
    return content.rstrip() + f"\n{replacement}\n"


def prepare_local_environment():
    """Create/repair only the local, git-ignored environment file."""
    process_env = (os.environ.get("FLASK_ENV") or "").strip().lower()
    if process_env == "production" or os.environ.get("RENDER"):
        return

    env_path = PROJECT_ROOT / ".env"
    env_example_path = PROJECT_ROOT / ".env.example"
    created = not env_path.exists()
    content = (
        env_example_path.read_text(encoding="utf-8")
        if created and env_example_path.exists()
        else env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    )

    match = re.search(r"^SECRET_KEY=(.*)$", content, re.MULTILINE)
    current_secret = match.group(1).strip() if match else ""
    unsafe = {
        "", "secret", "dev", "development", "change-this-secret-key",
        "change-this-to-a-long-random-secret-key",
    }
    changed = created
    if current_secret.lower() in unsafe or len(current_secret) < 32:
        content = _set_env_value(content, "SECRET_KEY", secrets.token_hex(32))
        changed = True
    # `run.py` is the local launcher. Keep local HTTP login cookies usable even
    # when `.env` was previously copied verbatim from the production example.
    if not re.search(r"^FLASK_ENV=development$", content, re.MULTILINE):
        content = _set_env_value(content, "FLASK_ENV", "development")
        changed = True
    if not re.search(r"^SESSION_COOKIE_SECURE=0$", content, re.MULTILINE):
        content = _set_env_value(content, "SESSION_COOKIE_SECURE", "0")
        changed = True

    if changed:
        env_path.write_text(content, encoding="utf-8")
        print("LOCAL SETUP: .env is ready with a private generated SECRET_KEY.")


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
            return

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
            print("DATABASE SETUP: legacy SQLite schema upgraded to Phase 20H.")
        else:
            print(
                "DATABASE SETUP STOPPED: this unstamped SQLite file is not a "
                "recognized full CMSE database, so it was not modified."
            )


if __name__ == "__main__":
    upgrade_local_sqlite_database()
    app.run(host="0.0.0.0", port=5000, debug=True)
