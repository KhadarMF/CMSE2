from datetime import date


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def _team_leader_setup():
    from app import db
    from app.models import Employee, Project, ProjectTeamAssignment, Team, User
    from werkzeug.security import generate_password_hash

    leader = User(
        full_name="Hodan Team Leader",
        email="hodan-team-leader@example.com",
        password_hash=generate_password_hash("Correct-Horse-Battery-1"),
        role="Team Leader",
        is_active=True,
    )
    outsider = User(
        full_name="Outside Requester",
        email="outside-requester@example.com",
        password_hash=generate_password_hash("Correct-Horse-Battery-1"),
        role="Employee",
        is_active=True,
    )
    db.session.add_all([leader, outsider])
    db.session.flush()

    employee = Employee(
        employee_code="TL-001",
        full_name=leader.full_name,
        email=leader.email,
        job_title="Team Leader",
        status="Active",
        user_id=leader.id,
    )
    db.session.add(employee)
    db.session.flush()

    team = Team(
        team_name="Hodan Solar Team",
        team_type="Installation",
        leader_employee_id=employee.id,
        status="Active",
    )
    other_team = Team(team_name="Unrelated Team", status="Active")
    db.session.add_all([team, other_team])
    db.session.flush()

    project = Project(
        project_name="Assigned Clinic Solar",
        customer_name="Assigned Clinic",
        location="Hargeisa",
        project_type="Hybrid Solar",
        status="Installation",
        created_by_id=outsider.id,
    )
    other_project = Project(
        project_name="Restricted Warehouse Solar",
        customer_name="Restricted Warehouse",
        location="Berbera",
        project_type="Grid Tie",
        status="Installation",
        created_by_id=outsider.id,
    )
    db.session.add_all([project, other_project])
    db.session.flush()
    db.session.add(ProjectTeamAssignment(
        project_id=project.id,
        team_id=team.id,
        status="Active",
        work_scope="Solar installation",
    ))
    db.session.commit()
    return leader, outsider, team, other_team, project, other_project


def test_team_leader_can_create_and_only_see_own_payment_requests(app, client):
    from app import db
    from app.models import PaymentRequest

    leader, outsider, team, _, project, other_project = _team_leader_setup()
    db.session.add(PaymentRequest(
        request_no="PR-OUTSIDE-001",
        requested_by_id=outsider.id,
        project_id=other_project.id,
        payee_name="Outside Vendor",
        purpose="Not visible to the Team Leader",
        amount=90,
        status="Pending Manager Approval",
    ))
    db.session.commit()
    outside_request = PaymentRequest.query.filter_by(request_no="PR-OUTSIDE-001").one()

    _login(client, leader)
    form_response = client.get("/payments/requests/create")
    form_html = form_response.get_data(as_text=True)
    assert form_response.status_code == 200
    assert team.team_name in form_html
    assert project.project_name in form_html
    assert "Unrelated Team" not in form_html
    assert other_project.project_name not in form_html

    response = client.post(
        "/payments/requests/create",
        data={
            "team_id": str(team.id),
            "project_id": str(project.id),
            "request_type": "Cash Advance",
            "category": "Project Expense",
            "payee_name": "Site Electrician",
            "purpose": "DC cable termination labour",
            "amount": "125.50",
            "currency": "USD",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    created = PaymentRequest.query.filter_by(requested_by_id=leader.id).one()
    assert created.team_id == team.id
    assert created.project_id == project.id
    assert created.request_type == "Cash Advance"
    assert created.status == "Pending Manager Approval"

    denied = client.get(
        f"/payments/requests/{outside_request.id}", follow_redirects=True
    )
    denied_html = denied.get_data(as_text=True)
    assert denied.status_code == 200
    assert "You can only view your own payment requests." in denied_html
    assert "Outside Vendor" not in denied_html


def test_team_leader_daily_report_is_project_scoped_and_unique(app, client):
    from app.models import DailySiteReport

    leader, _, team, other_team, project, other_project = _team_leader_setup()
    _login(client, leader)

    form_response = client.get("/forms/daily-site-report/new")
    form_html = form_response.get_data(as_text=True)
    assert form_response.status_code == 200
    assert team.team_name in form_html
    assert project.project_name in form_html
    assert other_team.team_name not in form_html
    assert other_project.project_name not in form_html

    report_day = date(2026, 8, 4).isoformat()
    payload = {
        "project_id": str(project.id),
        "team_id": str(team.id),
        "report_date": report_day,
        "approval_status": "Draft",
        "planned_activities": "Mount panels and terminate DC cables",
        "employees_present": "5",
        "employees_absent": "1",
        "normal_hours": "8",
        "overtime_hours": "1",
        "work_done_today": "Mounted 18 panels and completed string one.",
        "completed_quantity": "18",
        "quantity_unit": "panels",
        "progress_percentage": "45%",
        "safety_notes": "Toolbox talk completed.",
        "next_day_plan": "Complete strings two and three.",
    }
    created_response = client.post(
        "/forms/daily-site-report/new", data=payload, follow_redirects=True
    )
    assert created_response.status_code == 200
    report = DailySiteReport.query.filter_by(created_by_id=leader.id).one()
    assert report.team_id == team.id
    assert report.project_id == project.id
    assert report.site_supervisor == leader.full_name
    assert report.approval_status == "Draft"

    duplicate_response = client.post(
        "/forms/daily-site-report/new", data=payload, follow_redirects=True
    )
    assert duplicate_response.status_code == 400
    duplicate_html = duplicate_response.get_data(as_text=True)
    assert "already exists for this team, project, and date" in duplicate_html
    assert "Mounted 18 panels and completed string one." in duplicate_html
    assert DailySiteReport.query.filter_by(created_by_id=leader.id).count() == 1

    submit_response = client.post(
        f"/forms/daily-site-report/{report.id}/submit", follow_redirects=True
    )
    assert submit_response.status_code == 200
    assert DailySiteReport.query.get(report.id).approval_status == "Submitted"

    edit_response = client.get(
        f"/forms/daily-site-report/{report.id}/edit", follow_redirects=True
    )
    assert "You do not have permission to edit this form." in edit_response.get_data(as_text=True)


def test_team_leader_cannot_submit_for_an_unassigned_project(app, client):
    from app.models import DailySiteReport, PaymentRequest

    leader, _, team, _, _, other_project = _team_leader_setup()
    _login(client, leader)

    payment_response = client.post(
        "/payments/requests/create",
        data={
            "team_id": str(team.id),
            "project_id": str(other_project.id),
            "payee_name": "Blocked Vendor",
            "purpose": "Must not be saved",
            "amount": "50",
        },
        follow_redirects=True,
    )
    assert "Select a project assigned to your team." in payment_response.get_data(as_text=True)
    assert PaymentRequest.query.filter_by(requested_by_id=leader.id).count() == 0

    report_response = client.post(
        "/forms/daily-site-report/new",
        data={
            "project_id": str(other_project.id),
            "team_id": str(team.id),
            "report_date": "2026-08-04",
            "work_done_today": "Must not be saved",
        },
        follow_redirects=True,
    )
    assert "not assigned to that project" in report_response.get_data(as_text=True)
    assert DailySiteReport.query.filter_by(created_by_id=leader.id).count() == 0
