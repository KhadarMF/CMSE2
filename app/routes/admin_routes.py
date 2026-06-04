from pathlib import Path
from datetime import datetime
import shutil
from flask import Blueprint, render_template, send_file, flash, redirect, url_for, current_app, request
from flask_login import login_required, current_user
from app import db
from app.models import Notification, Branch, Department, CompanyProfile, User, UserFormPermission, FORM_PERMISSION_KEYS
from app.permissions import can_manage_users
from app.settings import get_email_config, set_setting
from app.notifications import send_email
from app.role_permissions import ROLE_PERMISSION_SUMMARY

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def require_admin():
    if not can_manage_users(current_user):
        flash("Only Admin can access this page.", "danger")
        return False
    return True

@admin_bp.route("/backup")
@login_required
def backup_home():
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    backups_dir = Path(current_app.root_path).parent / "backups"; backups_dir.mkdir(exist_ok=True)
    backups = sorted(backups_dir.glob("*.db"), reverse=True)
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(100).all()
    return render_template("admin/backup.html", backups=backups, notifications=notifications)

@admin_bp.route("/backup/create")
@login_required
def create_backup():
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    db_path = Path(current_app.instance_path) / "solar_documents.db"
    if not db_path.exists():
        flash("Database file not found.", "danger"); return redirect(url_for("admin.backup_home"))
    backups_dir = Path(current_app.root_path).parent / "backups"; backups_dir.mkdir(exist_ok=True)
    backup_file = backups_dir / f"solar_documents_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(db_path, backup_file)
    flash("Backup created successfully.", "success")
    return redirect(url_for("admin.backup_home"))

@admin_bp.route("/backup/download/<filename>")
@login_required
def download_backup(filename):
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    file_path = Path(current_app.root_path).parent / "backups" / filename
    if not file_path.exists():
        flash("Backup file not found.", "danger"); return redirect(url_for("admin.backup_home"))
    return send_file(file_path, as_attachment=True)

@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings_home():
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    if request.method == "POST":
        for key in ["MAIL_SERVER", "MAIL_PORT", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER"]:
            db.session.add(set_setting(key, request.form.get(key, "")))
        db.session.add(set_setting("MAIL_USE_TLS", "true" if request.form.get("MAIL_USE_TLS") == "on" else "false"))
        db.session.commit()
        flash("Email settings saved successfully.", "success")
        return redirect(url_for("admin.settings_home"))
    return render_template("admin/settings.html", cfg=get_email_config())

@admin_bp.route("/settings/test-email", methods=["POST"])
@login_required
def test_email():
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    to_email = request.form.get("test_email") or current_user.email
    try:
        send_email(to_email, "Solar Doc System Test Email", "This is a test email from the Solar Project Document & Approval Management System.")
        flash(f"Test email sent to {to_email}.", "success")
    except Exception as e:
        flash(f"Test email failed: {e}", "danger")
    return redirect(url_for("admin.settings_home"))

@admin_bp.route("/branches", methods=["GET", "POST"])
@login_required
def branches():
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    if request.method == "POST":
        db.session.add(Branch(branch_name=request.form.get("branch_name"), location=request.form.get("location"), is_active=True)); db.session.commit()
        flash("Branch created successfully.", "success"); return redirect(url_for("admin.branches"))
    return render_template("admin/branches.html", branches=Branch.query.order_by(Branch.branch_name.asc()).all())

@admin_bp.route("/branches/<int:branch_id>/toggle")
@login_required
def toggle_branch(branch_id):
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    branch = Branch.query.get_or_404(branch_id); branch.is_active = not branch.is_active; db.session.commit()
    flash("Branch status updated.", "success"); return redirect(url_for("admin.branches"))

@admin_bp.route("/departments", methods=["GET", "POST"])
@login_required
def departments():
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    if request.method == "POST":
        db.session.add(Department(department_name=request.form.get("department_name"), description=request.form.get("description"), is_active=True)); db.session.commit()
        flash("Department created successfully.", "success"); return redirect(url_for("admin.departments"))
    return render_template("admin/departments.html", departments=Department.query.order_by(Department.department_name.asc()).all())

@admin_bp.route("/departments/<int:department_id>/toggle")
@login_required
def toggle_department(department_id):
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    dept = Department.query.get_or_404(department_id); dept.is_active = not dept.is_active; db.session.commit()
    flash("Department status updated.", "success"); return redirect(url_for("admin.departments"))

@admin_bp.route("/permissions")
@login_required
def permissions_overview():
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    return render_template("admin/permissions.html", permissions=ROLE_PERMISSION_SUMMARY)


@admin_bp.route("/company", methods=["GET", "POST"])
@login_required
def company_profile():
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    company = CompanyProfile.query.first()
    if not company:
        company = CompanyProfile(company_name="Cadceed-Maal Solar Energy")
        db.session.add(company)
        db.session.commit()
    if request.method == "POST":
        company.company_name = request.form.get("company_name") or company.company_name
        company.tagline = request.form.get("tagline")
        company.address = request.form.get("address")
        company.phone = request.form.get("phone")
        company.email = request.form.get("email")
        company.website = request.form.get("website")
        company.tax_no = request.form.get("tax_no")
        company.logo_text = request.form.get("logo_text") or "CMSE"
        company.primary_color = request.form.get("primary_color") or "#f97316"
        company.secondary_color = request.form.get("secondary_color") or "#16a34a"
        db.session.commit()
        flash("Company profile saved successfully.", "success")
        return redirect(url_for("admin.company_profile"))
    return render_template("admin/company_profile.html", company=company)


@admin_bp.route("/form-permissions", methods=["GET", "POST"])
@login_required
def form_permissions():
    if not require_admin(): return redirect(url_for("dashboard.dashboard"))
    users = User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    selected_user_id = request.args.get("user_id") or request.form.get("user_id") or (users[0].id if users else None)
    selected_user = User.query.get(selected_user_id) if selected_user_id else None
    if request.method == "POST" and selected_user:
        # Phase 15P: Admin has permanent full access and should not be restricted by the matrix.
        # The matrix is only for non-admin users such as Technicians, Sales, Support, Managers, etc.
        if selected_user.role == "Admin":
            UserFormPermission.query.filter_by(user_id=selected_user.id).delete()
            db.session.commit()
            flash("Admin users always have FULL ACCESS. No manual permission rows are required for Admin.", "info")
            return redirect(url_for("admin.form_permissions", user_id=selected_user.id))

        # Rebuild permissions cleanly to avoid stale/duplicate rows.
        UserFormPermission.query.filter_by(user_id=selected_user.id).delete()
        saved_count = 0
        for item in FORM_PERMISSION_KEYS:
            key, label = item[0], item[1]
            has_any = any(request.form.get(f"{key}_{action}") == "on" for action in ["view", "create", "edit", "delete", "approve", "print_export"])
            if not has_any:
                continue
            perm = UserFormPermission(user_id=selected_user.id, form_key=key, form_label=label)
            perm.can_view = request.form.get(f"{key}_view") == "on"
            perm.can_create = request.form.get(f"{key}_create") == "on"
            perm.can_edit = request.form.get(f"{key}_edit") == "on"
            perm.can_delete = request.form.get(f"{key}_delete") == "on"
            perm.can_approve = request.form.get(f"{key}_approve") == "on"
            if hasattr(perm, "can_print_export"):
                perm.can_print_export = request.form.get(f"{key}_print_export") == "on"
            perm.updated_by_id = current_user.id
            db.session.add(perm)
            saved_count += 1
        db.session.commit()
        flash(f"User permissions saved successfully ({saved_count} permission rows). User must logout and login again.", "success")
        return redirect(url_for("admin.form_permissions", user_id=selected_user.id))
    existing = {}
    if selected_user:
        for p in UserFormPermission.query.filter_by(user_id=selected_user.id).all():
            existing[p.form_key] = p
    return render_template("admin/form_permissions.html", users=users, selected_user=selected_user, forms=FORM_PERMISSION_KEYS, existing=existing)
