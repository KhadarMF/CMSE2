"""Phase 20D test harness.

Each test gets a throwaway SQLite database built by running the real Alembic
migrations - not db.create_all(). If a migration is broken, the tests fail,
which is the whole point.
"""
import os
import tempfile

import pytest

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-key-not-used-in-production-0123456789")


@pytest.fixture()
def app(monkeypatch, tmp_path):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.delenv("ADMIN_RECOVERY_PASSWORD", raising=False)

    from app import create_app, db
    application = create_app()
    # CSRF is exercised explicitly in the csrf_app fixture; the rest of the
    # suite turns it off so tests read as behaviour, not token plumbing.
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with application.app_context():
        from flask_migrate import upgrade
        upgrade()
        yield application
        db.session.remove()
        # Windows keeps the SQLite file locked until the pooled engine is
        # disposed; without this the otherwise-passing suite fails teardown.
        db.engine.dispose()

    os.unlink(path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_app(monkeypatch, tmp_path):
    """Same as `app` but with CSRF left ON, for the CSRF tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.delenv("ADMIN_RECOVERY_PASSWORD", raising=False)

    from app import create_app, db
    application = create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=True)

    with application.app_context():
        from flask_migrate import upgrade
        upgrade()
        yield application
        db.session.remove()
        db.engine.dispose()

    os.unlink(path)


@pytest.fixture()
def user(app):
    from app import db
    from app.models import User
    from werkzeug.security import generate_password_hash
    u = User(full_name="Test Finance", email="finance@example.com",
             password_hash=generate_password_hash("Correct-Horse-Battery-1"),
             role="Finance Officer", is_active=True)
    db.session.add(u)
    db.session.commit()
    return u
