"""Phase 20D: the three critical fixes, proven rather than asserted."""
import os
import pytest


# ---------------------------------------------------------------------------
# 1. SECRET_KEY
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_key", [
    "",
    "change-this-secret-key",
    "change-this-to-a-long-random-secret-key",
    "short",
    "a" * 31,
])
def test_production_refuses_weak_secret_key(bad_key):
    from app.security import validate_secret_key
    old = os.environ.pop("FLASK_ENV", None)
    try:
        with pytest.raises(RuntimeError):
            validate_secret_key(bad_key)
    finally:
        if old is not None:
            os.environ["FLASK_ENV"] = old


def test_production_accepts_strong_secret_key():
    from app.security import validate_secret_key
    old = os.environ.pop("FLASK_ENV", None)
    try:
        validate_secret_key("b" * 64)  # must not raise
    finally:
        if old is not None:
            os.environ["FLASK_ENV"] = old


def test_development_still_boots_without_secret_key():
    from app.security import validate_secret_key
    os.environ["FLASK_ENV"] = "development"
    validate_secret_key("")  # must not raise


# ---------------------------------------------------------------------------
# 2. CSRF
# ---------------------------------------------------------------------------

def test_post_without_csrf_token_is_rejected(csrf_app):
    client = csrf_app.test_client()
    resp = client.post("/login", data={"email": "a@b.c", "password": "x"})
    assert resp.status_code == 400, "a POST with no CSRF token must not be accepted"


def test_login_form_renders_a_csrf_token(csrf_app):
    client = csrf_app.test_client()
    html = client.get("/login").get_data(as_text=True)
    assert 'name="csrf_token"' in html


def test_whatsapp_webhook_is_exempt(csrf_app):
    """Meta posts to this endpoint with no browser session, so it must not
    be CSRF-protected - otherwise inbound WhatsApp silently breaks."""
    client = csrf_app.test_client()
    resp = client.post("/whatsapp/webhook", json={"object": "whatsapp_business_account"})
    assert resp.status_code != 400


def test_backup_creation_rejects_get(app):
    """A state-changing GET is reachable from a plain <img> tag and is not
    covered by CSRF protection."""
    client = app.test_client()
    resp = client.get("/admin/backup/create")
    assert resp.status_code == 405 or resp.status_code == 302


# ---------------------------------------------------------------------------
# 3. Login throttling
# ---------------------------------------------------------------------------

def test_repeated_failures_lock_the_account(app, user):
    from app.security import login_lockout_status, record_failed_login, LOGIN_MAX_ATTEMPTS_PER_EMAIL
    with app.test_request_context("/login", environ_base={"REMOTE_ADDR": "10.0.0.9"}):
        locked, _, _ = login_lockout_status("finance@example.com")
        assert not locked

        for _ in range(LOGIN_MAX_ATTEMPTS_PER_EMAIL):
            record_failed_login("finance@example.com")

        locked, minutes, reason = login_lockout_status("finance@example.com")
        assert locked
        assert reason == "account"
        assert minutes >= 1


def test_successful_login_clears_the_counter(app, user):
    from app.security import (record_failed_login, clear_failed_logins,
                              login_lockout_status, LOGIN_MAX_ATTEMPTS_PER_EMAIL)
    with app.test_request_context("/login", environ_base={"REMOTE_ADDR": "10.0.0.9"}):
        for _ in range(LOGIN_MAX_ATTEMPTS_PER_EMAIL):
            record_failed_login("finance@example.com")
        assert login_lockout_status("finance@example.com")[0]

        clear_failed_logins("finance@example.com")
        assert not login_lockout_status("finance@example.com")[0]


def test_lockout_does_not_leak_across_accounts(app, user):
    """Locking one email must not lock a different colleague out."""
    from app.security import record_failed_login, login_lockout_status, LOGIN_MAX_ATTEMPTS_PER_EMAIL
    with app.test_request_context("/login", environ_base={"REMOTE_ADDR": "10.0.0.9"}):
        for _ in range(LOGIN_MAX_ATTEMPTS_PER_EMAIL):
            record_failed_login("finance@example.com")
        assert login_lockout_status("finance@example.com")[0]
        assert not login_lockout_status("sales@example.com")[0]


def test_login_endpoint_returns_429_when_locked(app, user):
    from app.security import LOGIN_MAX_ATTEMPTS_PER_EMAIL
    client = app.test_client()
    for _ in range(LOGIN_MAX_ATTEMPTS_PER_EMAIL):
        client.post("/login", data={"email": "finance@example.com", "password": "wrong"})
    resp = client.post("/login", data={"email": "finance@example.com", "password": "wrong"})
    assert resp.status_code == 429


def test_correct_password_still_works(app, user):
    client = app.test_client()
    resp = client.post("/login",
                       data={"email": "finance@example.com", "password": "Correct-Horse-Battery-1"},
                       follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" not in resp.headers.get("Location", "")
