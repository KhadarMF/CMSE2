from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Project, PROJECT_STATUSES, Customer, ProjectType, Team
from app.permissions import can_create_project, can_create_form, can_access_module
from app.project_command_center import build_project_command_center
from app.milestone_service import ensure_default_milestones, project_completion_ready
from app.team_leader_access import assigned_projects_for_user, is_team_leader, team_leader_can_access_project

project_bp = Blueprint("projects", __name__, url_prefix="/projects")

def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()

@project_bp.route("/")
@login_required
def list_projects():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    active = request.args.get("active", "").strip()

    query = Project.query
    if is_team_leader(current_user) and not can_access_module(current_user, "projects", "view"):
        query = query.filter(Project.id.in_([item.id for item in assigned_projects_for_user(current_user)]))
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Project.project_name.ilike(like))
            | (Project.customer_name.ilike(like))
            | (Project.location.ilike(like))
        )
    if status:
        query = query.filter_by(status=status)
    elif active == "1":
        query = query.filter(Project.status != "Completed")

    projects = query.order_by(Project.created_at.desc()).all()
    return render_template(
        "projects/list.html",
        projects=projects,
        statuses=PROJECT_STATUSES,
        selected_status=status,
        active=active,
        search=search,
    )

@project_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_project():
    if not can_create_project(current_user):
        flash("Only Admin or Operation Manager can create projects.", "danger")
        return redirect(url_for("projects.list_projects"))

    if request.method == "POST":
        requested_status = request.form.get("status", "New")
        if requested_status not in PROJECT_STATUSES or requested_status == "Completed":
            flash("Create the project in an active phase; completion requires approved milestones.", "danger")
            return redirect(url_for("projects.create_project"))
        project = Project(
            project_name=request.form.get("project_name"),
            customer_name=request.form.get("customer_name"),
            location=request.form.get("location"),
            project_type=request.form.get("project_type"),
            capacity=request.form.get("capacity"),
            start_date=parse_date(request.form.get("start_date")),
            expected_completion_date=parse_date(request.form.get("expected_completion_date")),
            status=requested_status,
            assigned_team=request.form.get("assigned_team"),
            description=request.form.get("description"),
            created_by_id=current_user.id,
        )
        db.session.add(project)
        db.session.flush()
        ensure_default_milestones(project, current_user.id)
        db.session.commit()
        flash("Project created successfully.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template("projects/create.html", statuses=[status for status in PROJECT_STATUSES if status != "Completed"], customers=Customer.query.filter_by(is_active=True).order_by(Customer.customer_name.asc()).all(), project_types=ProjectType.query.filter_by(is_active=True).order_by(ProjectType.type_name.asc()).all(), teams=Team.query.filter_by(status="Active").order_by(Team.team_name.asc()).all())

@project_bp.route("/<int:project_id>")
@login_required
def detail(project_id):
    project = Project.query.get_or_404(project_id)
    if not can_access_module(current_user, "projects", "view") and not team_leader_can_access_project(current_user, project):
        flash("You can only open projects assigned to a team you lead.", "danger")
        return redirect(url_for("projects.list_projects"))
    allowed_forms = {
        "site-survey": can_create_form(current_user, "site-survey"),
        "solar-pump-survey": can_create_form(current_user, "solar-pump-survey"),
        "load-assessment": can_create_form(current_user, "load-assessment"),
        "daily-site-report": can_create_form(current_user, "daily-site-report"),
        "delivery-note": can_create_form(current_user, "delivery-note"),
        "testing": can_create_form(current_user, "testing"),
        "commissioning": can_create_form(current_user, "commissioning"),
        "handover": can_create_form(current_user, "handover"),
    }
    command_center = build_project_command_center(project)
    return render_template(
        "projects/detail.html",
        project=project,
        allowed_forms=allowed_forms,
        command_center=command_center,
        active_project_context=project,
    )

@project_bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)

    if not can_access_module(current_user, "projects", "edit"):
        flash("Only Admin or Operation Manager can edit projects.", "danger")
        return redirect(url_for("projects.detail", project_id=project.id))

    if request.method == "POST":

        customer_name = request.form.get("customer_name", "").strip()
        if customer_name and not Customer.query.filter_by(customer_name=customer_name).first():
            db.session.add(Customer(customer_name=customer_name, customer_type="Project Customer", is_active=True))
            db.session.flush()
        project.project_name = request.form.get("project_name")
        project.customer_name = customer_name
        project.location = request.form.get("location")
        project.project_type = request.form.get("project_type")
        project.capacity = request.form.get("capacity")
        project.start_date = parse_date(request.form.get("start_date"))
        project.expected_completion_date = parse_date(request.form.get("expected_completion_date"))
        requested_status = request.form.get("status")
        if requested_status == "Completed" and not project_completion_ready(project):
            flash("Project completion is blocked until all configured milestones are completed or formally overridden.", "danger")
            return redirect(url_for("projects.detail", project_id=project.id) + "#milestones")
        project.status = requested_status
        project.assigned_team = request.form.get("assigned_team")
        project.description = request.form.get("description")
        db.session.commit()
        flash("Project updated successfully.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template("projects/edit.html", project=project, statuses=PROJECT_STATUSES, customers=Customer.query.filter_by(is_active=True).order_by(Customer.customer_name.asc()).all(), project_types=ProjectType.query.filter_by(is_active=True).order_by(ProjectType.type_name.asc()).all(), teams=Team.query.filter_by(status="Active").order_by(Team.team_name.asc()).all())
