"""Phase 20D - security hardening.

Three things live here:

1. validate_secret_key()  - refuses to boot in production with a guessable
   SECRET_KEY. Previously the app fell back to the string
   "change-this-secret-key", which means anyone who reads the source can
   forge a session cookie and become Admin.

2. init_csrf()            - global CSRF protection. Every state-changing
   POST now requires a token. Endpoints that are legitimately called by
   outside systems (the Meta WhatsApp webhook) are exempted explicitly.

3. Login throttling       - failed logins are recorded and both the email
   and the source IP are locked out after too many failures.
"""
import os
from datetime import datetime, timedelta

from flask import request
from flask_wtf.csrf import CSRFProtect, CSRFError

csrf = CSRFProtect()

# Values that must never be accepted as a real secret in production.
UNSAFE_SECRET_KEYS = {
    "",
    "change-this-secret-key",
    "change-this-to-a-long-random-secret-key",
    "secret",
    "dev",
    "development",
}

MIN_SECRET_KEY_LENGTH = 32

# Login throttle settings (overridable by environment).
LOGIN_MAX_ATTEMPTS_PER_EMAIL = int(os.environ.get("LOGIN_MAX_ATTEMPTS_PER_EMAIL", "5"))
LOGIN_MAX_ATTEMPTS_PER_IP = int(os.environ.get("LOGIN_MAX_ATTEMPTS_PER_IP", "20"))
LOGIN_WINDOW_MINUTES = int(os.environ.get("LOGIN_WINDOW_MINUTES", "15"))
LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))


def is_production():
    """Production unless explicitly told otherwise.

    Failing safe matters here: if FLASK_ENV is unset on Render because
    somebody forgot it, we want the strict checks, not the lax ones.
    """
    env = (os.environ.get("FLASK_ENV") or "").strip().lower()
    if env in ("development", "dev", "testing", "test", "local"):
        return False
    if (os.environ.get("CMSE_ALLOW_INSECURE_SECRET", "").strip().lower()
            in ("1", "true", "yes")):
        return False
    return True


def validate_secret_key(secret_key):
    """Raise RuntimeError rather than boot an ERP with a forgeable session.

    A silent fallback here is worse than downtime: the app looks healthy
    while every session cookie in it can be minted by a stranger.
    """
    if not is_production():
        return

    value = (secret_key or "").strip()
    if value.lower() in UNSAFE_SECRET_KEYS:
        raise RuntimeError(
            "SECRET_KEY is missing or still set to the default placeholder. "
            "The app will not start in production. Generate one with:\n"
            "    python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            "then set it as the SECRET_KEY environment variable."
        )
    if len(value) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY is only {len(value)} characters. At least "
            f"{MIN_SECRET_KEY_LENGTH} are required in production. Generate one with:\n"
            "    python -c \"import secrets; print(secrets.token_hex(32))\""
        )


def init_csrf(app):
    """Turn on CSRF for every POST, then exempt the few endpoints that are
    called by machines rather than by a logged-in browser."""
    app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)   # token lives as long as the session
    app.config.setdefault("WTF_CSRF_SSL_STRICT", False)  # Render terminates TLS at the proxy
    csrf.init_app(app)

    # The Meta WhatsApp webhook is an unauthenticated POST from Facebook's
    # servers. It has no browser session and therefore no CSRF token; it is
    # authenticated separately by the verify token / signature check in
    # whatsapp_routes.
    from app.routes.whatsapp_routes import webhook_receive
    csrf.exempt(webhook_receive)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(err):
        from flask import flash, redirect, url_for, render_template
        app.logger.warning("CSRF rejected: %s %s from %s",
                           request.method, request.path, client_ip())
        try:
            flash(
                "Your session expired or the form was submitted from an "
                "untrusted page. Please log in again and retry.",
                "danger",
            )
            return redirect(url_for("auth.login")), 400
        except Exception:
            return render_template("auth/login.html"), 400


def client_ip():
    """Real client IP behind Render's proxy.

    request.remote_addr is the proxy, so every user would share one bucket
    and the IP throttle would lock out the whole company at once.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.remote_addr or "unknown")[:64]


# ---------------------------------------------------------------------------
# Login throttling
# ---------------------------------------------------------------------------

def _window_start():
    return datetime.utcnow() - timedelta(minutes=LOGIN_WINDOW_MINUTES)


def record_failed_login(email):
    from app import db
    from app.models import LoginAttempt
    try:
        db.session.add(LoginAttempt(
            email=(email or "").strip().lower()[:255],
            ip_address=client_ip(),
            user_agent=(request.headers.get("User-Agent") or "")[:255],
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def clear_failed_logins(email):
    from app import db
    from app.models import LoginAttempt
    try:
        LoginAttempt.query.filter(
            LoginAttempt.email == (email or "").strip().lower()
        ).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()


def login_lockout_status(email):
    """Return (is_locked, minutes_remaining, reason).

    Fails open on database errors - a broken throttle table must not lock
    the whole company out of its own ERP.
    """
    from app.models import LoginAttempt
    email = (email or "").strip().lower()
    try:
        since = _window_start()

        by_email = 0
        if email:
            by_email = LoginAttempt.query.filter(
                LoginAttempt.email == email,
                LoginAttempt.attempted_at >= since,
            ).count()

        by_ip = LoginAttempt.query.filter(
            LoginAttempt.ip_address == client_ip(),
            LoginAttempt.attempted_at >= since,
        ).count()

        if by_email >= LOGIN_MAX_ATTEMPTS_PER_EMAIL:
            latest = LoginAttempt.query.filter(
                LoginAttempt.email == email
            ).order_by(LoginAttempt.attempted_at.desc()).first()
            return True, _minutes_left(latest), "account"

        if by_ip >= LOGIN_MAX_ATTEMPTS_PER_IP:
            latest = LoginAttempt.query.filter(
                LoginAttempt.ip_address == client_ip()
            ).order_by(LoginAttempt.attempted_at.desc()).first()
            return True, _minutes_left(latest), "network"

    except Exception:
        return False, 0, None

    return False, 0, None


def _minutes_left(latest_attempt):
    if not latest_attempt or not latest_attempt.attempted_at:
        return LOGIN_LOCKOUT_MINUTES
    unlock_at = latest_attempt.attempted_at + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
    remaining = (unlock_at - datetime.utcnow()).total_seconds() / 60
    return max(1, int(remaining) + 1)


def purge_old_login_attempts(days=30):
    """Housekeeping so the table does not grow without bound."""
    from app import db
    from app.models import LoginAttempt
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        LoginAttempt.query.filter(
            LoginAttempt.attempted_at < cutoff
        ).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
