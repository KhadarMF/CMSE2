"""Team Leader identity and project-scope helpers.

Team leadership is data, not a broad role string: a user is a Team Leader when
their active Employee record is selected as ``Team.leader_employee_id``.  This
keeps self-service access limited to the teams and projects the administrator
actually assigned to that person.
"""

from sqlalchemy import or_

from app.models import Employee, Project, ProjectTeamAssignment, Team


def employee_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return Employee.query.filter_by(user_id=user.id, status="Active").first()


def led_teams_for_user(user, active_only=True):
    employee = employee_for_user(user)
    if not employee:
        return []
    query = Team.query.filter_by(leader_employee_id=employee.id)
    if active_only:
        query = query.filter_by(status="Active")
    return query.order_by(Team.team_name.asc()).all()


def is_team_leader(user):
    return bool(led_teams_for_user(user))


def led_team_ids(user):
    return {team.id for team in led_teams_for_user(user)}


def assigned_projects_for_user(user):
    """Projects assigned through Project Workforce or legacy assigned_team."""
    teams = led_teams_for_user(user)
    if not teams:
        return []
    team_ids = [team.id for team in teams]
    team_names = [team.team_name for team in teams]
    assignment_ids = (
        ProjectTeamAssignment.query.with_entities(ProjectTeamAssignment.project_id)
        .filter(
            ProjectTeamAssignment.team_id.in_(team_ids),
            ProjectTeamAssignment.status == "Active",
        )
    )
    return (
        Project.query.filter(
            or_(
                Project.id.in_(assignment_ids),
                Project.assigned_team.in_(team_names),
            )
        )
        .order_by(Project.project_name.asc())
        .all()
    )


def team_is_assigned_to_project(team, project):
    if not team or not project:
        return False
    assignment = ProjectTeamAssignment.query.filter_by(
        team_id=team.id, project_id=project.id, status="Active"
    ).first()
    return bool(assignment or project.assigned_team == team.team_name)


def user_leads_team(user, team_id):
    try:
        team_id = int(team_id)
    except (TypeError, ValueError):
        return False
    return team_id in led_team_ids(user)


def user_can_report_for(user, team_id, project_id):
    if not user_leads_team(user, team_id):
        return False
    team = Team.query.get(int(team_id))
    project = Project.query.get(int(project_id)) if project_id else None
    return team_is_assigned_to_project(team, project)


def team_leader_can_access_daily_report(user, report):
    return bool(
        report
        and report.team_id
        and user_leads_team(user, report.team_id)
    )


def team_leader_can_access_payment(user, payment_request):
    return bool(
        payment_request
        and payment_request.requested_by_id == getattr(user, "id", None)
    )


def is_team_leader_self_service_endpoint(endpoint, method="GET", view_args=None):
    """Endpoints whose route-level ownership checks make leader bypass safe."""
    view_args = view_args or {}
    payment_endpoints = {
        "payments.dashboard",
        "payments.my_requests",
        "payments.create_request",
        "payments.request_detail",
        "payments.download_attachment",
        "payments.cancel_request",
    }
    if endpoint in payment_endpoints:
        return True

    if endpoint == "forms.forms_home":
        return True
    if view_args.get("form_key") != "daily-site-report":
        return False
    return endpoint in {
        "forms.list_forms",
        "forms.create_form",
        "forms.view_form",
        "forms.edit_form",
        "forms.submit_form",
        "forms.print_form",
    }
