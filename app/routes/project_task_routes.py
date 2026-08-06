from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Project, ProjectMilestone, ProjectTask, User, Employee, TeamMember, TASK_STATUSES, TASK_PRIORITIES
from app.activity import log_activity
from app.milestone_service import mark_milestone_started
from app.permissions import can_access_module
from app.team_leader_access import assigned_projects_for_user, is_team_leader, led_teams_for_user, team_leader_can_access_project
from sqlalchemy import text

project_task_bp = Blueprint("project_tasks", __name__, url_prefix="/project-tasks")

MANAGE_ROLES = ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"]

@project_task_bp.before_app_request
def ensure_task_assignment_columns():
    # Safe local migration for existing databases. It adds missing columns only.
    try:
        inspector = db.inspect(db.engine)
        cols = [c["name"] for c in inspector.get_columns("project_task")]
        if "assigned_employee_id" not in cols:
            db.session.execute(text("ALTER TABLE project_task ADD COLUMN assigned_employee_id INTEGER"))
        if "supervisor_user_id" not in cols:
            db.session.execute(text("ALTER TABLE project_task ADD COLUMN supervisor_user_id INTEGER"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()

def can_manage_tasks(user):
    return user.role in MANAGE_ROLES


def task_self_service_mode():
    return is_team_leader(current_user) and not can_access_module(current_user, "project-tasks", "view")


def allowed_task_projects():
    return assigned_projects_for_user(current_user) if task_self_service_mode() else Project.query.order_by(Project.project_name.asc()).all()


def allowed_task_employees():
    if not task_self_service_mode():
        return Employee.query.filter_by(status="Active").order_by(Employee.full_name.asc()).all()
    teams = led_teams_for_user(current_user)
    team_ids = [team.id for team in teams]
    employee_ids = {team.leader_employee_id for team in teams if team.leader_employee_id}
    if team_ids:
        employee_ids.update(
            row.employee_id for row in TeamMember.query.filter(
                TeamMember.team_id.in_(team_ids), TeamMember.is_active.is_(True)
            ).all()
        )
    return Employee.query.filter(Employee.id.in_(employee_ids), Employee.status == "Active").order_by(Employee.full_name.asc()).all() if employee_ids else []


def valid_milestone(project_id, milestone_id):
    if not milestone_id:
        return None
    return ProjectMilestone.query.filter_by(id=int(milestone_id), project_id=int(project_id)).first()

@project_task_bp.route("/")
@login_required
def list_tasks():
    status = request.args.get("status", "").strip()
    project_id = request.args.get("project_id", "").strip()
    mine = request.args.get("mine", "").strip()
    overdue = request.args.get("overdue", "").strip()
    employee_id = request.args.get("employee_id", "").strip()
    query = ProjectTask.query
    if task_self_service_mode():
        project_ids = [item.id for item in assigned_projects_for_user(current_user)]
        query = query.filter(ProjectTask.project_id.in_(project_ids))
    if status:
        query = query.filter_by(status=status)
    if project_id:
        query = query.filter_by(project_id=int(project_id))
    if employee_id:
        query = query.filter_by(assigned_employee_id=int(employee_id))
    if mine == "1":
        query = query.filter((ProjectTask.supervisor_user_id == current_user.id) | (ProjectTask.assigned_to_id == current_user.id))
    if overdue == "1":
        query = query.filter(
            ProjectTask.due_date < datetime.utcnow().date(),
            ProjectTask.status.notin_(["Completed", "Cancelled"]),
        )
    tasks = query.order_by(ProjectTask.due_date.asc().nullslast(), ProjectTask.created_at.desc()).all()
    projects = allowed_task_projects()
    employees = allowed_task_employees()
    return render_template("project_tasks/list.html", tasks=tasks, projects=projects, employees=employees, statuses=TASK_STATUSES, selected_status=status, selected_project_id=project_id, selected_employee_id=employee_id, mine=mine, overdue=overdue)

@project_task_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_task():
    if not (can_manage_tasks(current_user) or is_team_leader(current_user)):
        flash("You do not have permission to create project tasks.", "danger")
        return redirect(url_for("project_tasks.list_tasks"))
    projects = allowed_task_projects()
    users = [current_user] if task_self_service_mode() else User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    employees = allowed_task_employees()
    project_ids = {item.id for item in projects}
    milestones = ProjectMilestone.query.filter(ProjectMilestone.project_id.in_(project_ids)).order_by(ProjectMilestone.project_id, ProjectMilestone.sequence).all() if project_ids else []
    selected_project_id = request.args.get("project_id", "")
    if request.method == "POST":
        project_id = int(request.form.get("project_id"))
        project = Project.query.get_or_404(project_id)
        if task_self_service_mode() and not team_leader_can_access_project(current_user, project):
            flash("You can only create tasks for a project assigned to a team you lead.", "danger")
            return redirect(url_for("project_tasks.list_tasks"))
        milestone = valid_milestone(project_id, request.form.get("milestone_id"))
        if request.form.get("milestone_id") and not milestone:
            flash("Selected milestone does not belong to this project.", "danger")
            return redirect(request.url)
        assigned_employee_id = int(request.form.get("assigned_employee_id")) if request.form.get("assigned_employee_id") else None
        if task_self_service_mode() and assigned_employee_id not in {item.id for item in employees}:
            flash("Assigned employee must belong to a team you lead.", "danger")
            return redirect(request.url)
        supervisor_id = current_user.id if task_self_service_mode() else (int(request.form.get("supervisor_user_id")) if request.form.get("supervisor_user_id") else None)
        task = ProjectTask(
            project_id=project_id,
            milestone_id=milestone.id if milestone else None,
            milestone_required=request.form.get("milestone_required") == "on",
            milestone_critical=request.form.get("milestone_critical") == "on",
            title=request.form.get("title"),
            description=request.form.get("description"),
            # Phase 14E: employee performs the task; supervisor user follows it in the system.
            assigned_employee_id=assigned_employee_id,
            supervisor_user_id=supervisor_id,
            # Legacy assigned_to_id mirrors supervisor for old reports/filters.
            assigned_to_id=supervisor_id,
            created_by_id=current_user.id,
            status=request.form.get("status", "Not Started"),
            priority=request.form.get("priority", "Normal"),
            start_date=parse_date(request.form.get("start_date")),
            due_date=parse_date(request.form.get("due_date")),
            progress_percent=int(request.form.get("progress_percent") or 0),
            remarks=request.form.get("remarks"),
        )
        if task.status == "Completed":
            task.completed_at = datetime.utcnow()
            task.progress_percent = 100
        db.session.add(task)
        db.session.flush()
        mark_milestone_started(task.milestone_id)
        log_activity("Create", "Project Task", task.id, f"Created task: {task.title}")
        db.session.commit()
        flash("Project task created successfully.", "success")
        return redirect(url_for("project_tasks.list_tasks", project_id=task.project_id))
    return render_template("project_tasks/form.html", task=None, projects=projects, milestones=milestones, users=users, employees=employees, statuses=TASK_STATUSES, priorities=TASK_PRIORITIES, selected_project_id=selected_project_id, selected_milestone_id=request.args.get("milestone_id", ""), team_leader_mode=task_self_service_mode())

@project_task_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = ProjectTask.query.get_or_404(task_id)
    if not (can_manage_tasks(current_user) or task.supervisor_user_id == current_user.id or task.assigned_to_id == current_user.id or team_leader_can_access_project(current_user, task.project)):
        flash("You do not have permission to edit this task.", "danger")
        return redirect(url_for("project_tasks.list_tasks"))
    projects = allowed_task_projects() if task_self_service_mode() else Project.query.order_by(Project.project_name.asc()).all()
    users = [current_user] if task_self_service_mode() else User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    employees = allowed_task_employees()
    project_ids = {item.id for item in projects}
    milestones = ProjectMilestone.query.filter(ProjectMilestone.project_id.in_(project_ids)).order_by(ProjectMilestone.project_id, ProjectMilestone.sequence).all() if project_ids else []
    if request.method == "POST":
        old_status = task.status
        if can_manage_tasks(current_user):
            task.project_id = int(request.form.get("project_id"))
            milestone = valid_milestone(task.project_id, request.form.get("milestone_id"))
            if request.form.get("milestone_id") and not milestone:
                flash("Selected milestone does not belong to this project.", "danger")
                return redirect(request.url)
            task.milestone_id = milestone.id if milestone else None
            mark_milestone_started(task.milestone_id)
            task.milestone_required = request.form.get("milestone_required") == "on"
            task.milestone_critical = request.form.get("milestone_critical") == "on"
            task.title = request.form.get("title")
            task.description = request.form.get("description")
            task.assigned_employee_id = int(request.form.get("assigned_employee_id")) if request.form.get("assigned_employee_id") else None
            task.supervisor_user_id = int(request.form.get("supervisor_user_id")) if request.form.get("supervisor_user_id") else None
            task.assigned_to_id = int(request.form.get("supervisor_user_id")) if request.form.get("supervisor_user_id") else None
            task.priority = request.form.get("priority", "Normal")
            task.start_date = parse_date(request.form.get("start_date"))
            task.due_date = parse_date(request.form.get("due_date"))
        task.status = request.form.get("status", task.status)
        task.progress_percent = int(request.form.get("progress_percent") or 0)
        task.remarks = request.form.get("remarks")
        if task.status == "Completed" and old_status != "Completed":
            task.completed_at = datetime.utcnow()
            task.progress_percent = 100
        if task.status != "Completed":
            task.completed_at = None
        log_activity("Update", "Project Task", task.id, f"Updated task: {task.title}")
        db.session.commit()
        flash("Task updated successfully.", "success")
        return redirect(url_for("project_tasks.list_tasks", project_id=task.project_id))
    return render_template("project_tasks/form.html", task=task, projects=projects, milestones=milestones, users=users, employees=employees, statuses=TASK_STATUSES, priorities=TASK_PRIORITIES, selected_project_id=task.project_id, selected_milestone_id=task.milestone_id or "", team_leader_mode=task_self_service_mode())

@project_task_bp.route("/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = ProjectTask.query.get_or_404(task_id)
    if not can_manage_tasks(current_user):
        flash("Only managers can delete tasks.", "danger")
        return redirect(url_for("project_tasks.list_tasks"))
    project_id = task.project_id
    title = task.title
    db.session.delete(task)
    log_activity("Delete", "Project Task", task_id, f"Deleted task: {title}")
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("project_tasks.list_tasks", project_id=project_id))


@project_task_bp.route("/employee/<int:employee_id>/report")
@login_required
def employee_task_report(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    tasks = ProjectTask.query.filter_by(assigned_employee_id=employee.id).order_by(ProjectTask.created_at.desc()).all()
    summary = {
        "total": len(tasks),
        "completed": len([t for t in tasks if t.status == "Completed"]),
        "open": len([t for t in tasks if t.status not in ["Completed", "Cancelled"]]),
        "overdue": len([t for t in tasks if t.is_overdue]),
    }
    return render_template("project_tasks/employee_report.html", employee=employee, tasks=tasks, summary=summary)
