from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.activity import log_activity
from app.milestone_service import (
    approve_milestone, build_milestone_snapshot, ensure_default_milestones,
    override_milestone, reopen_milestone, submit_milestone,
)
from app.models import (
    DOCUMENT_TYPES, MILESTONE_STATUSES, Document, MilestoneDocumentRequirement,
    Project, ProjectMilestone, Team, User,
)
from app.notifications import notify_roles, notify_user
from app.permissions import can_access_module
from app.team_leader_access import team_leader_can_access_project


milestone_bp = Blueprint("milestones", __name__, url_prefix="/project-milestones")

CONFIGURE_ROLES = {"Admin", "Management", "Operation Manager"}
APPROVE_ROLES = {"Admin", "Management", "Operation Manager"}
OVERRIDE_ROLES = {"Admin", "Management", "Operation Manager"}
FORM_REQUIREMENT_CHOICES = (
    ("", "Uploaded document"),
    ("site-survey", "Site Survey & Load Assessment"),
    ("solar-pump-survey", "Solar Pumping Site Survey"),
    ("load-assessment", "Load Assessment"),
    ("daily-site-report", "Daily Site Report"),
    ("delivery-note", "Delivery Note"),
    ("testing", "Testing Form"),
    ("commissioning", "Commissioning Form"),
    ("handover", "Handover Form"),
)


def _parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _can_configure():
    return current_user.role in CONFIGURE_ROLES


def _can_approve():
    return current_user.role in APPROVE_ROLES


def _can_view_project(project):
    return can_access_module(current_user, "project-milestones", "view") or team_leader_can_access_project(current_user, project)


def _can_submit(project):
    return _can_configure() or team_leader_can_access_project(current_user, project)


def _deny(project=None, message="You do not have permission for this milestone action."):
    flash(message, "danger")
    return redirect(url_for("projects.detail", project_id=project.id) if project else url_for("dashboard.dashboard"))


@milestone_bp.route("/project/<int:project_id>/initialize", methods=["POST"])
@login_required
def initialize_project(project_id):
    project = Project.query.get_or_404(project_id)
    if not _can_configure():
        return _deny(project)
    if project.milestones:
        flash("This project already has milestones.", "warning")
    else:
        ensure_default_milestones(project, current_user.id)
        log_activity("Initialize", "Project Milestones", project.id, "Created the standard six-milestone template.")
        db.session.commit()
        flash("Six evidence-based milestones were added to the project.", "success")
    return redirect(url_for("projects.detail", project_id=project.id) + "#milestones")


@milestone_bp.route("/<int:milestone_id>")
@login_required
def detail(milestone_id):
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    project = milestone.project
    if not _can_view_project(project):
        return _deny(project)
    snapshot = build_milestone_snapshot(milestone)
    documents = Document.query.filter_by(project_id=project.id).order_by(Document.upload_date.desc()).all()
    return render_template(
        "milestones/detail.html",
        milestone=milestone,
        project=project,
        snapshot=snapshot,
        all_tasks=sorted(project.tasks, key=lambda item: (item.due_date or datetime.max.date(), item.id)),
        all_materials=sorted(project.material_requests, key=lambda item: (item.request_date or datetime.min.date(), item.id)),
        all_documents=documents,
        all_reports=sorted(project.daily_reports, key=lambda item: (item.report_date or datetime.min.date(), item.id), reverse=True),
        all_issues=sorted(project.issues, key=lambda item: (item.severity != "Critical", item.id)),
        teams=Team.query.filter_by(status="Active").order_by(Team.team_name.asc()).all(),
        users=User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all(),
        document_types=DOCUMENT_TYPES,
        form_requirement_choices=FORM_REQUIREMENT_CHOICES,
        statuses=MILESTONE_STATUSES,
        can_configure=_can_configure(),
        can_submit=_can_submit(project),
        can_approve=_can_approve(),
        can_override=current_user.role in OVERRIDE_ROLES,
    )


@milestone_bp.route("/<int:milestone_id>/edit", methods=["POST"])
@login_required
def edit(milestone_id):
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    if not _can_configure():
        return _deny(milestone.project)
    weights = {
        "project_weight": _int(request.form.get("project_weight")),
        "physical_weight": _int(request.form.get("physical_weight")),
        "procurement_weight": _int(request.form.get("procurement_weight")),
        "document_weight": _int(request.form.get("document_weight")),
    }
    if any(value < 0 or value > 100 for value in weights.values()):
        flash("Every weight must be between 0 and 100.", "danger")
        return redirect(url_for("milestones.detail", milestone_id=milestone.id))
    dimension_total = weights["physical_weight"] + weights["procurement_weight"] + weights["document_weight"]
    if dimension_total != 100:
        flash("Physical + Procurement + Documents must total 100%. Use 0% for N/A.", "danger")
        return redirect(url_for("milestones.detail", milestone_id=milestone.id))
    milestone.name = (request.form.get("name") or milestone.name).strip()
    milestone.description = request.form.get("description")
    milestone.sequence = max(1, _int(request.form.get("sequence"), milestone.sequence))
    for key, value in weights.items():
        setattr(milestone, key, value)
    milestone.planned_start = _parse_date(request.form.get("planned_start"))
    milestone.planned_end = _parse_date(request.form.get("planned_end"))
    if milestone.planned_start and milestone.planned_end and milestone.planned_end < milestone.planned_start:
        flash("Planned end date cannot be before the start date.", "danger")
        return redirect(url_for("milestones.detail", milestone_id=milestone.id))
    milestone.responsible_team_id = _int(request.form.get("responsible_team_id")) or None
    milestone.responsible_user_id = _int(request.form.get("responsible_user_id")) or None
    milestone.requires_daily_report = request.form.get("requires_daily_report") == "on"
    if milestone.status == "Not Started":
        milestone.status = "In Progress"
    log_activity("Update", "Project Milestone", milestone.id, f"Updated milestone: {milestone.name}")
    db.session.commit()
    flash("Milestone configuration saved.", "success")
    return redirect(url_for("milestones.detail", milestone_id=milestone.id))


@milestone_bp.route("/<int:milestone_id>/link-records", methods=["POST"])
@login_required
def link_records(milestone_id):
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    if not _can_configure():
        return _deny(milestone.project)
    project = milestone.project
    groups = (
        (project.tasks, "task_ids"),
        (project.material_requests, "material_ids"),
        (project.documents, "document_ids"),
        (project.daily_reports, "report_ids"),
        (project.issues, "issue_ids"),
    )
    for records, field_name in groups:
        selected = {_int(value) for value in request.form.getlist(field_name)}
        for record in records:
            if record.milestone_id == milestone.id and record.id not in selected:
                record.milestone_id = None
            elif record.id in selected:
                record.milestone_id = milestone.id
    for task in project.tasks:
        if task.milestone_id == milestone.id:
            task.milestone_required = request.form.get(f"task_required_{task.id}") == "on"
            task.milestone_critical = request.form.get(f"task_critical_{task.id}") == "on"
    for item in project.material_requests:
        if item.milestone_id == milestone.id:
            item.milestone_required = request.form.get(f"material_required_{item.id}") == "on"
            item.milestone_critical = request.form.get(f"material_critical_{item.id}") == "on"
    if milestone.status == "Not Started":
        milestone.status = "In Progress"
    log_activity("Link", "Project Milestone", milestone.id, "Updated milestone evidence links.")
    db.session.commit()
    flash("Linked records and gate flags saved.", "success")
    return redirect(url_for("milestones.detail", milestone_id=milestone.id))


@milestone_bp.route("/<int:milestone_id>/requirements/add", methods=["POST"])
@login_required
def add_requirement(milestone_id):
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    if not _can_configure():
        return _deny(milestone.project)
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Requirement title is required.", "danger")
        return redirect(url_for("milestones.detail", milestone_id=milestone.id))
    form_key = request.form.get("form_key") or None
    document_type = None if form_key else (request.form.get("document_type") or None)
    document_id = _int(request.form.get("document_id")) or None
    if document_id:
        document = Document.query.get(document_id)
        if not document or document.project_id != milestone.project_id:
            flash("Selected document does not belong to this project.", "danger")
            return redirect(url_for("milestones.detail", milestone_id=milestone.id))
    is_critical = request.form.get("is_critical") == "on"
    requirement = MilestoneDocumentRequirement(
        milestone_id=milestone.id,
        title=title,
        form_key=form_key,
        document_type=document_type,
        document_id=document_id,
        is_required=request.form.get("is_required") == "on" or is_critical,
        is_critical=is_critical,
        notes=request.form.get("notes"),
    )
    db.session.add(requirement)
    if milestone.status == "Not Started":
        milestone.status = "In Progress"
    db.session.commit()
    flash("Document/form requirement added.", "success")
    return redirect(url_for("milestones.detail", milestone_id=milestone.id))


@milestone_bp.route("/<int:milestone_id>/requirements/<int:requirement_id>/delete", methods=["POST"])
@login_required
def delete_requirement(milestone_id, requirement_id):
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    if not _can_configure():
        return _deny(milestone.project)
    requirement = MilestoneDocumentRequirement.query.filter_by(id=requirement_id, milestone_id=milestone.id).first_or_404()
    db.session.delete(requirement)
    db.session.commit()
    flash("Requirement removed.", "success")
    return redirect(url_for("milestones.detail", milestone_id=milestone.id))


@milestone_bp.route("/<int:milestone_id>/submit", methods=["POST"])
@login_required
def submit(milestone_id):
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    if not _can_submit(milestone.project):
        return _deny(milestone.project)
    ok, snapshot = submit_milestone(milestone, current_user)
    if ok:
        notify_roles(
            ["Admin", "Management", "Operation Manager"],
            subject=f"Milestone ready: {milestone.name}",
            message=f"{current_user.full_name} submitted {milestone.project.project_name} / {milestone.name} for approval.",
            module="project-milestones", record_id=milestone.id,
        )
        flash("All gates passed. Milestone submitted for manager approval.", "success")
    else:
        flash(f"Completion blocked by {len(snapshot['blockers'])} gate(s). Review the checklist below.", "danger")
    db.session.commit()
    return redirect(url_for("milestones.detail", milestone_id=milestone.id))


@milestone_bp.route("/<int:milestone_id>/approve", methods=["POST"])
@login_required
def approve(milestone_id):
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    if not _can_approve():
        return _deny(milestone.project)
    ok, snapshot, message = approve_milestone(milestone, current_user)
    if ok and milestone.submitted_by:
        notify_user(
            milestone.submitted_by,
            subject=f"Milestone approved: {milestone.name}",
            message=f"{current_user.full_name} approved {milestone.project.project_name} / {milestone.name}.",
            module="project-milestones", record_id=milestone.id,
        )
    db.session.commit()
    flash(message, "success" if ok else "danger")
    return redirect(url_for("milestones.detail", milestone_id=milestone.id))


@milestone_bp.route("/<int:milestone_id>/override", methods=["POST"])
@login_required
def override(milestone_id):
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    if current_user.role not in OVERRIDE_ROLES:
        return _deny(milestone.project)
    ok, snapshot, message = override_milestone(milestone, current_user, request.form.get("reason"))
    db.session.commit()
    flash(message, "warning" if ok else "danger")
    return redirect(url_for("milestones.detail", milestone_id=milestone.id))


@milestone_bp.route("/<int:milestone_id>/reopen", methods=["POST"])
@login_required
def reopen(milestone_id):
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    if current_user.role not in OVERRIDE_ROLES:
        return _deny(milestone.project)
    ok, message = reopen_milestone(milestone, current_user, request.form.get("reason"))
    db.session.commit()
    flash(message, "success" if ok else "danger")
    return redirect(url_for("milestones.detail", milestone_id=milestone.id))
