from datetime import date


def _login(client, user):
    from flask import g
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    g.pop("_login_user", None)


def _users_and_project():
    from app import db
    from app.milestone_service import ensure_default_milestones
    from app.models import Employee, Project, ProjectTeamAssignment, Team, User
    from werkzeug.security import generate_password_hash

    admin = User(
        full_name="Milestone Admin", email="milestone-admin@example.com",
        password_hash=generate_password_hash("Correct-Horse-Battery-1"),
        role="Admin", is_active=True,
    )
    leader = User(
        full_name="Milestone Team Leader", email="milestone-leader@example.com",
        password_hash=generate_password_hash("Correct-Horse-Battery-1"),
        role="Team Leader", is_active=True,
    )
    db.session.add_all([admin, leader])
    db.session.flush()
    employee = Employee(
        employee_code="MILE-TL-1", full_name=leader.full_name,
        email=leader.email, job_title="Team Leader", status="Active",
        user_id=leader.id,
    )
    db.session.add(employee)
    db.session.flush()
    team = Team(
        team_name="Milestone Delivery Team", team_type="Installation",
        leader_employee_id=employee.id, status="Active",
    )
    db.session.add(team)
    db.session.flush()
    project = Project(
        project_name="Evidence Solar Project", customer_name="Evidence Customer",
        location="Hargeisa", project_type="Hybrid Solar",
        start_date=date(2026, 8, 1), expected_completion_date=date(2026, 10, 1),
        status="Survey", created_by_id=admin.id,
    )
    db.session.add(project)
    db.session.flush()
    db.session.add(ProjectTeamAssignment(
        project_id=project.id, team_id=team.id, status="Active",
        work_scope="Milestone delivery",
    ))
    ensure_default_milestones(project, admin.id)
    db.session.commit()
    return admin, leader, team, project


def test_default_template_has_simple_weighted_milestones_and_na_dimensions(app):
    from app import db
    from app.milestone_service import build_milestone_snapshot, mark_milestone_started
    from app.models import ProjectTask, SiteSurveyForm

    admin, _, _, project = _users_and_project()
    assert len(project.milestones) == 8
    assert sum(item.project_weight for item in project.milestones) == 100

    survey = next(item for item in project.milestones if item.code == "SURVEY")
    db.session.add_all([
        ProjectTask(
            project_id=project.id, milestone_id=survey.id,
            milestone_required=True, milestone_critical=True,
            title="Complete site survey", created_by_id=admin.id,
            status="Completed", progress_percent=100,
        ),
        ProjectTask(
            project_id=project.id, milestone_id=survey.id,
            milestone_required=False, milestone_critical=False,
            title="Optional survey photo cleanup", created_by_id=admin.id,
            status="Not Started", progress_percent=0,
        ),
        SiteSurveyForm(
            project_id=project.id, created_by_id=admin.id,
            survey_date=date(2026, 8, 1), approval_status="Approved",
        ),
    ])
    db.session.commit()
    mark_milestone_started(survey.id)
    db.session.commit()

    snapshot = build_milestone_snapshot(survey)
    assert survey.status == "In Progress"
    assert snapshot["components"]["procurement"]["applicable"] is False
    assert snapshot["components"]["procurement"]["progress"] is None
    assert snapshot["raw_progress"] == 100
    assert snapshot["ready"] is True


def test_team_leader_submits_and_manager_approves_only_after_gates_pass(app, client):
    from app import db
    from app.milestone_service import approve_milestone
    from app.models import ProjectTask, SiteSurveyForm

    admin, leader, _, project = _users_and_project()
    survey = next(item for item in project.milestones if item.code == "SURVEY")
    db.session.add_all([
        ProjectTask(
            project_id=project.id, milestone_id=survey.id,
            milestone_required=True, title="Survey site",
            created_by_id=leader.id, supervisor_user_id=leader.id,
            status="Completed", progress_percent=100,
        ),
        SiteSurveyForm(
            project_id=project.id, created_by_id=leader.id,
            survey_date=date(2026, 8, 2), approval_status="Approved",
        ),
    ])
    db.session.commit()

    _login(client, leader)
    view = client.get(f"/project-milestones/{survey.id}")
    assert view.status_code == 200
    assert "Automatic completion gates" in view.get_data(as_text=True)
    submitted = client.post(
        f"/project-milestones/{survey.id}/submit", follow_redirects=True
    )
    assert submitted.status_code == 200
    assert survey.status == "Ready for Approval"
    assert survey.submitted_by_id == leader.id

    self_approved, _, message = approve_milestone(survey, leader)
    assert self_approved is False
    assert "cannot approve" in message

    _login(client, admin)
    approved = client.post(
        f"/project-milestones/{survey.id}/approve", follow_redirects=True
    )
    assert approved.status_code == 200
    assert survey.status == "Completed"
    assert survey.approved_by_id == admin.id
    assert any(item.action == "Approve" for item in survey.audit_logs)


def test_system_blocks_missing_evidence_and_supports_audited_exception(app, client):
    from app.milestone_service import build_milestone_snapshot

    admin, leader, _, project = _users_and_project()
    installation = next(item for item in project.milestones if item.code == "INSTALLATION")

    _login(client, leader)
    blocked = client.post(
        f"/project-milestones/{installation.id}/submit", follow_redirects=True
    )
    assert blocked.status_code == 200
    assert installation.status == "Blocked"
    assert "Completion blocked" in blocked.get_data(as_text=True)

    _login(client, admin)
    overridden = client.post(
        f"/project-milestones/{installation.id}/override",
        data={"reason": "Customer emergency requires controlled early handover."},
        follow_redirects=True,
    )
    assert overridden.status_code == 200
    assert installation.status == "Completed with Exception"
    assert build_milestone_snapshot(installation)["progress"] == 0
    assert installation.override_by_id == admin.id
    assert "Customer emergency" in installation.override_reason
    assert any(item.action == "Emergency override" for item in installation.audit_logs)


def test_project_cannot_be_marked_completed_until_every_milestone_is_closed(app, client):
    from app import db
    from app.milestone_service import override_milestone

    admin, _, _, project = _users_and_project()
    _login(client, admin)
    blocked = client.post(
        f"/projects/{project.id}/edit",
        data={
            "project_name": project.project_name,
            "customer_name": project.customer_name,
            "location": project.location,
            "project_type": project.project_type,
            "status": "Completed",
        },
        follow_redirects=True,
    )
    assert blocked.status_code == 200
    assert project.status != "Completed"
    assert "Project completion is blocked" in blocked.get_data(as_text=True)

    for milestone in project.milestones:
        ok, _, _ = override_milestone(
            milestone, admin,
            "Approved legacy closeout exception for controlled migration.",
        )
        assert ok
    db.session.commit()
    assert project.status == "Completed"


def test_site_survey_delete_handles_milestone_links_without_500(app, client):
    from app import db
    from app.models import SiteSurveyForm

    admin, _, _, project = _users_and_project()
    survey_milestone = next(item for item in project.milestones if item.code == "SURVEY")
    entry = SiteSurveyForm(
        project_id=project.id,
        created_by_id=admin.id,
        survey_date=date(2026, 8, 3),
        approval_status="Approved",
    )
    db.session.add(entry)
    db.session.flush()
    requirement = next(
        item for item in survey_milestone.document_requirements
        if item.form_key == "site-survey"
    )
    requirement.form_record_id = entry.id
    db.session.commit()

    _login(client, admin)
    get_response = client.get(f"/forms/site-survey/{entry.id}/delete")
    assert get_response.status_code == 302
    assert f"/forms/site-survey/{entry.id}" in get_response.headers["Location"]

    delete_response = client.post(f"/forms/site-survey/{entry.id}/delete")
    assert delete_response.status_code == 302
    assert delete_response.headers["Location"].endswith("/forms/site-survey")
    assert db.session.get(SiteSurveyForm, entry.id) is None
    assert requirement.form_record_id is None
