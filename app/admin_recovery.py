"""Emergency admin account recovery for Cadceed-Maal ERP.

This module is intentionally disabled unless ADMIN_RECOVERY_PASSWORD is set.
It only updates/creates one Admin user and does not touch customer/project data.
"""
import os
from werkzeug.security import generate_password_hash


def run_admin_recovery_if_requested(app):
    """Reset/create an Admin user when recovery env vars are present.

    Render usage:
      ADMIN_RECOVERY_EMAIL=admin@cadceedmaal.com
      ADMIN_RECOVERY_PASSWORD=<new strong password>

    Remove ADMIN_RECOVERY_PASSWORD after successful login.
    """
    password = os.environ.get("ADMIN_RECOVERY_PASSWORD", "").strip()
    if not password:
        return

    email = os.environ.get("ADMIN_RECOVERY_EMAIL", "admin@cadceedmaal.com").strip().lower()
    full_name = os.environ.get("ADMIN_RECOVERY_FULL_NAME", "System Administrator").strip() or "System Administrator"

    if len(password) < 8:
        app.logger.error("ADMIN_RECOVERY_PASSWORD is set but too short. Use at least 8 characters.")
        return

    try:
        from app import db
        from app.models import User

        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = generate_password_hash(password)
            user.role = "Admin"
            user.is_active = True
            if not user.full_name:
                user.full_name = full_name
            action = "reset"
        else:
            user = User(
                full_name=full_name,
                email=email,
                password_hash=generate_password_hash(password),
                role="Admin",
                is_active=True,
            )
            db.session.add(user)
            action = "created"

        db.session.commit()
        app.logger.warning(
            "ADMIN RECOVERY APPLIED: admin account %s for %s. Remove ADMIN_RECOVERY_PASSWORD from environment after login.",
            action,
            email,
        )
    except Exception:
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        app.logger.exception("ADMIN RECOVERY FAILED")
