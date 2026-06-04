from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Project, ProjectIssue, User, ISSUE_STATUSES, ISSUE_SEVERITIES
from app.activity import log_activity

issue_bp = Blueprint("issues", __name__, url_prefix="/issues")
MANAGE_ROLES = ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"]
ISSUE_TYPES = ["General", "Technical", "Material", "Transport", "Finance", "Safety", "Customer", "Delay", "Quality"]

def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()

def can_manage_issues(user):
    return user.role in MANAGE_ROLES

@issue_bp.route("/")
@login_required
def list_issues():
    status = request.args.get("status", "").strip()
    severity = request.args.get("severity", "").strip()
    project_id = request.args.get("project_id", "").strip()
    query = ProjectIssue.query
    if status:
        query = query.filter_by(status=status)
    if severity:
        query = query.filter_by(severity=severity)
    if project_id:
        query = query.filter_by(project_id=int(project_id))
    issues = query.order_by(ProjectIssue.reported_at.desc()).all()
    projects = Project.query.order_by(Project.project_name.asc()).all()
    return render_template("issues/list.html", issues=issues, projects=projects, statuses=ISSUE_STATUSES, severities=ISSUE_SEVERITIES, selected_status=status, selected_severity=severity, selected_project_id=project_id)

@issue_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_issue():
    projects = Project.query.order_by(Project.project_name.asc()).all()
    users = User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    selected_project_id = request.args.get("project_id", "")
    if request.method == "POST":
        issue = ProjectIssue(
            project_id=int(request.form.get("project_id")),
            title=request.form.get("title"),
            description=request.form.get("description"),
            issue_type=request.form.get("issue_type", "General"),
            severity=request.form.get("severity", "Medium"),
            status=request.form.get("status", "Open"),
            responsible_user_id=int(request.form.get("responsible_user_id")) if request.form.get("responsible_user_id") else None,
            reported_by_id=current_user.id,
            target_resolution_date=parse_date(request.form.get("target_resolution_date")),
            resolution_notes=request.form.get("resolution_notes"),
        )
        if issue.status in ["Resolved", "Closed"]:
            issue.resolved_at = datetime.utcnow()
        db.session.add(issue)
        db.session.flush()
        log_activity("Create", "Project Issue", issue.id, f"Reported issue: {issue.title}")
        db.session.commit()
        flash("Issue created successfully.", "success")
        return redirect(url_for("issues.list_issues", project_id=issue.project_id))
    return render_template("issues/form.html", issue=None, projects=projects, users=users, statuses=ISSUE_STATUSES, severities=ISSUE_SEVERITIES, issue_types=ISSUE_TYPES, selected_project_id=selected_project_id)

@issue_bp.route("/<int:issue_id>/edit", methods=["GET", "POST"])
@login_required
def edit_issue(issue_id):
    issue = ProjectIssue.query.get_or_404(issue_id)
    if not (can_manage_issues(current_user) or issue.reported_by_id == current_user.id or issue.responsible_user_id == current_user.id):
        flash("You do not have permission to edit this issue.", "danger")
        return redirect(url_for("issues.list_issues"))
    projects = Project.query.order_by(Project.project_name.asc()).all()
    users = User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    if request.method == "POST":
        old_status = issue.status
        if can_manage_issues(current_user) or issue.reported_by_id == current_user.id:
            issue.project_id = int(request.form.get("project_id"))
            issue.title = request.form.get("title")
            issue.description = request.form.get("description")
            issue.issue_type = request.form.get("issue_type", "General")
            issue.severity = request.form.get("severity", "Medium")
            issue.responsible_user_id = int(request.form.get("responsible_user_id")) if request.form.get("responsible_user_id") else None
            issue.target_resolution_date = parse_date(request.form.get("target_resolution_date"))
        issue.status = request.form.get("status", issue.status)
        issue.resolution_notes = request.form.get("resolution_notes")
        if issue.status in ["Resolved", "Closed"] and old_status not in ["Resolved", "Closed"]:
            issue.resolved_at = datetime.utcnow()
        if issue.status not in ["Resolved", "Closed"]:
            issue.resolved_at = None
        log_activity("Update", "Project Issue", issue.id, f"Updated issue: {issue.title}")
        db.session.commit()
        flash("Issue updated successfully.", "success")
        return redirect(url_for("issues.list_issues", project_id=issue.project_id))
    return render_template("issues/form.html", issue=issue, projects=projects, users=users, statuses=ISSUE_STATUSES, severities=ISSUE_SEVERITIES, issue_types=ISSUE_TYPES, selected_project_id=issue.project_id)

@issue_bp.route("/<int:issue_id>/delete", methods=["POST"])
@login_required
def delete_issue(issue_id):
    issue = ProjectIssue.query.get_or_404(issue_id)
    if not can_manage_issues(current_user):
        flash("Only managers can delete issues.", "danger")
        return redirect(url_for("issues.list_issues"))
    project_id = issue.project_id
    title = issue.title
    db.session.delete(issue)
    log_activity("Delete", "Project Issue", issue_id, f"Deleted issue: {title}")
    db.session.commit()
    flash("Issue deleted.", "success")
    return redirect(url_for("issues.list_issues", project_id=project_id))
