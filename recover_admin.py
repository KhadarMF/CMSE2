"""One-off admin password recovery command.

Usage in Render Shell or locally:
    python recover_admin.py admin@cadceedmaal.com 'NewStrongPassword123!'

If email is omitted, admin@cadceedmaal.com is used.
"""
import sys
from werkzeug.security import generate_password_hash
from app import create_app, db
from app.models import User

email = sys.argv[1].strip().lower() if len(sys.argv) >= 2 else "admin@cadceedmaal.com"
password = sys.argv[2] if len(sys.argv) >= 3 else None

if not password or len(password) < 8:
    print("ERROR: Provide a new password with at least 8 characters.")
    print("Example: python recover_admin.py admin@cadceedmaal.com 'NewStrongPassword123!'")
    raise SystemExit(1)

app = create_app()
with app.app_context():
    user = User.query.filter_by(email=email).first()
    if user:
        user.password_hash = generate_password_hash(password)
        user.role = "Admin"
        user.is_active = True
        action = "reset"
    else:
        user = User(
            full_name="System Administrator",
            email=email,
            password_hash=generate_password_hash(password),
            role="Admin",
            is_active=True,
        )
        db.session.add(user)
        action = "created"
    db.session.commit()
    print(f"Admin account {action}: {email}")
    print("You can now login with the new password.")
