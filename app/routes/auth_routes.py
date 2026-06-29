from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models import User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))
    return redirect(url_for("auth.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Phase 17B.2A Security Fix:
    # Only redirect to dashboard when this browser session was authenticated
    # through the current safe login flow. Old cookies from previous builds are cleared.
    if current_user.is_authenticated and session.get("cmse_logged_in") is True:
        return redirect(url_for("dashboard.dashboard"))
    if current_user.is_authenticated and session.get("cmse_logged_in") is not True:
        logout_user()
        session.clear()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.is_active and check_password_hash(user.password_hash, password):
            session.clear()
            login_user(user, remember=False, fresh=True)
            session["cmse_logged_in"] = True
            session["cmse_user_id"] = user.id
            session["cmse_login_build"] = "17B.2A"
            flash("Login successful.", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("//") and not next_url.startswith("/auth"):
                return redirect(next_url)
            return redirect(url_for("dashboard.dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("auth.login"))
