from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Project, PROJECT_STATUSES, Customer, ProjectType, Team
from app.permissions import can_create_project, can_create_form

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

    query = Project.query
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Project.project_name.ilike(like))
            | (Project.customer_name.ilike(like))
            | (Project.location.ilike(like))
        )
    if status:
        query = query.filter_by(status=status)

    projects = query.order_by(Project.created_at.desc()).all()
    return render_template(
        "projects/list.html",
        projects=projects,
        statuses=PROJECT_STATUSES,
        selected_status=status,
        search=search,
    )

@project_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_project():
    if not can_create_project(current_user):
        flash("Only Admin or Operation Manager can create projects.", "danger")
        return redirect(url_for("projects.list_projects"))

    if request.method == "POST":
        project = Project(
            project_name=request.form.get("project_name"),
            customer_name=request.form.get("customer_name"),
            location=request.form.get("location"),
            project_type=request.form.get("project_type"),
            capacity=request.form.get("capacity"),
            start_date=parse_date(request.form.get("start_date")),
            expected_completion_date=parse_date(request.form.get("expected_completion_date")),
            status=request.form.get("status", "New"),
            assigned_team=request.form.get("assigned_team"),
            description=request.form.get("description"),
            created_by_id=current_user.id,
        )
        db.session.add(project)
        db.session.commit()
        flash("Project created successfully.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template("projects/create.html", statuses=PROJECT_STATUSES, customers=Customer.query.filter_by(is_active=True).order_by(Customer.customer_name.asc()).all(), project_types=ProjectType.query.filter_by(is_active=True).order_by(ProjectType.type_name.asc()).all(), teams=Team.query.filter_by(status="Active").order_by(Team.team_name.asc()).all())

@project_bp.route("/<int:project_id>")
@login_required
def detail(project_id):
    project = Project.query.get_or_404(project_id)
    allowed_forms = {
        "site-survey": can_create_form(current_user, "site-survey"),
        "load-assessment": can_create_form(current_user, "load-assessment"),
        "daily-site-report": can_create_form(current_user, "daily-site-report"),
        "delivery-note": can_create_form(current_user, "delivery-note"),
        "testing": can_create_form(current_user, "testing"),
        "commissioning": can_create_form(current_user, "commissioning"),
        "handover": can_create_form(current_user, "handover"),
    }
    return render_template("projects/detail.html", project=project, allowed_forms=allowed_forms)

@project_bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)

    if not can_create_project(current_user):
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
        project.status = request.form.get("status")
        project.assigned_team = request.form.get("assigned_team")
        project.description = request.form.get("description")
        db.session.commit()
        flash("Project updated successfully.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template("projects/edit.html", project=project, statuses=PROJECT_STATUSES, customers=Customer.query.filter_by(is_active=True).order_by(Customer.customer_name.asc()).all(), project_types=ProjectType.query.filter_by(is_active=True).order_by(ProjectType.type_name.asc()).all(), teams=Team.query.filter_by(status="Active").order_by(Team.team_name.asc()).all())
