from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app import db
from app.models import User, ROLES, Branch, Department
from app.permissions import can_manage_users

user_bp = Blueprint("users", __name__, url_prefix="/users")

def active_branches(): return Branch.query.filter_by(is_active=True).order_by(Branch.branch_name.asc()).all()
def active_departments(): return Department.query.filter_by(is_active=True).order_by(Department.department_name.asc()).all()

@user_bp.route("/")
@login_required
def list_users():
    if not can_manage_users(current_user): flash("Only Admin can manage users.", "danger"); return redirect(url_for("dashboard.dashboard"))
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users/list.html", users=users)

@user_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_user():
    if not can_manage_users(current_user): flash("Only Admin can create users.", "danger"); return redirect(url_for("dashboard.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if User.query.filter_by(email=email).first(): flash("This email already exists.", "danger"); return redirect(request.url)
        user = User(full_name=request.form.get("full_name"), email=email, password_hash=generate_password_hash(request.form.get("password")), role=request.form.get("role"), is_active=True if request.form.get("is_active") == "on" else False, branch_id=request.form.get("branch_id") or None, department_id=request.form.get("department_id") or None)
        db.session.add(user); db.session.commit(); flash("User created successfully.", "success"); return redirect(url_for("users.list_users"))
    return render_template("users/create.html", roles=ROLES, branches=active_branches(), departments=active_departments())

@user_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    if not can_manage_users(current_user): flash("Only Admin can edit users.", "danger"); return redirect(url_for("dashboard.dashboard"))
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing: flash("This email already exists for another user.", "danger"); return redirect(request.url)
        user.full_name = request.form.get("full_name"); user.email = email; user.role = request.form.get("role")
        user.is_active = True if request.form.get("is_active") == "on" else False
        user.branch_id = request.form.get("branch_id") or None; user.department_id = request.form.get("department_id") or None
        db.session.commit(); flash("User updated successfully.", "success"); return redirect(url_for("users.list_users"))
    return render_template("users/edit.html", user=user, roles=ROLES, branches=active_branches(), departments=active_departments())

@user_bp.route("/<int:user_id>/change-password", methods=["GET", "POST"])
@login_required
def change_password(user_id):
    if not can_manage_users(current_user): flash("Only Admin can change user passwords.", "danger"); return redirect(url_for("dashboard.dashboard"))
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        password = request.form.get("password"); confirm = request.form.get("confirm_password")
        if not password or password != confirm: flash("Passwords do not match.", "danger"); return redirect(request.url)
        user.password_hash = generate_password_hash(password); db.session.commit(); flash("Password changed successfully.", "success"); return redirect(url_for("users.list_users"))
    return render_template("users/change_password.html", user=user)

@user_bp.route("/<int:user_id>/toggle")
@login_required
def toggle_user(user_id):
    if not can_manage_users(current_user): flash("Only Admin can enable or disable users.", "danger"); return redirect(url_for("dashboard.dashboard"))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id: flash("You cannot disable your own account.", "danger"); return redirect(url_for("users.list_users"))
    user.is_active = not user.is_active; db.session.commit(); flash("User status updated.", "success"); return redirect(url_for("users.list_users"))
