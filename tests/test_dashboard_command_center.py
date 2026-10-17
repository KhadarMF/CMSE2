from datetime import date, timedelta


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def _user(email, role):
    from app.models import User
    from werkzeug.security import generate_password_hash

    return User(
        full_name=f"{role} Dashboard User",
        email=email,
        password_hash=generate_password_hash("Correct-Horse-Battery-1"),
        role=role,
        is_active=True,
    )


def test_dashboard_command_center_renders_operational_metrics_and_csv(app, client):
    from app import db
    from app.models import (
        DailySiteReport,
        Document,
        MaterialRequest,
        PaymentRequest,
        Project,
        ProjectIssue,
        ProjectTask,
        SalesQuotation,
        SalesQuotationLine,
    )

    admin = _user("dashboard-admin@example.com", "Admin")
    db.session.add(admin)
    db.session.flush()

    project = Project(
        project_name="Command Center Solar Site",
        customer_name="Dashboard Customer",
        location="Hargeisa",
        project_type="Hybrid Solar",
        status="Installation",
        start_date=date.today() - timedelta(days=30),
        expected_completion_date=date.today() - timedelta(days=1),
        created_by_id=admin.id,
    )
    db.session.add(project)
    db.session.flush()

    db.session.add_all(
        [
            DailySiteReport(
                project_id=project.id,
                created_by_id=admin.id,
                report_date=date.today(),
                approval_status="Approved",
                progress_percentage="55",
                work_done_today="Installed PV mounting structure",
            ),
            ProjectTask(
                project_id=project.id,
                title="Complete inverter cabling",
                created_by_id=admin.id,
                status="In Progress",
                priority="High",
                progress_percent=40,
                due_date=date.today() - timedelta(days=1),
            ),
            ProjectIssue(
                project_id=project.id,
                title="Critical delivery constraint",
                severity="Critical",
                status="Open",
                reported_by_id=admin.id,
                target_resolution_date=date.today(),
            ),
            Document(
                project_id=project.id,
                document_title="Updated site drawing",
                document_type="Technical Design",
                uploaded_by_id=admin.id,
                file_name="drawing.pdf",
                stored_file_name="dashboard-drawing.pdf",
                approval_status="Submitted",
            ),
            MaterialRequest(
                ref_no="MR-DASHBOARD-001",
                project_id=project.id,
                request_date=date.today(),
                status="Submitted",
                requested_by_id=admin.id,
            ),
            PaymentRequest(
                request_no="PR-DASHBOARD-001",
                requested_by_id=admin.id,
                project_id=project.id,
                request_type="Team Expense",
                payee_name="Dashboard Supplier",
                category="Operations",
                purpose="Site transport",
                amount=600,
                currency="USD",
                status="Pending Manager Approval",
            ),
        ]
    )
    quotation = SalesQuotation(
        ref_no="QT-DASHBOARD-001",
        project_id=project.id,
        quotation_date=date.today(),
        customer_name=project.customer_name,
        status="Approved by Customer",
        prepared_by_id=admin.id,
    )
    db.session.add(quotation)
    db.session.flush()
    db.session.add(
        SalesQuotationLine(
            quotation_id=quotation.id,
            item="Solar installation",
            quantity=1,
            unit="Lot",
            unit_price=2000,
        )
    )
    db.session.commit()

    _login(client, admin)
    response = client.get("/dashboard")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Dashboard Command Center" in html
    assert "Command Center Solar Site" in html
    assert "Project Portfolio 360" in html
    assert "AI Executive Summary" in html
    assert "Financial Overview" in html
    assert "Critical delivery constraint" not in html  # counted, then opened through drilldown
    assert "Critical Issues" in html
    assert "cc-kpi cc-kpi-danger" in html
    assert "/dashboard/export.csv" in html

    csv_response = client.get("/dashboard/export.csv")
    csv_text = csv_response.get_data(as_text=True)
    assert csv_response.status_code == 200
    assert csv_response.mimetype == "text/csv"
    assert "Command Center Solar Site" in csv_text
    assert "Revenue USD" in csv_text
    assert "2000.00" in csv_text


def test_team_leader_dashboard_is_project_scoped_and_hides_financials(app, client):
    from app import db
    from app.models import Employee, Project, ProjectTeamAssignment, Team

    leader = _user("dashboard-leader@example.com", "Team Leader")
    admin = _user("dashboard-owner@example.com", "Admin")
    db.session.add_all([leader, admin])
    db.session.flush()

    employee = Employee(
        employee_code="EMP-DASH-LEADER",
        full_name="Dashboard Team Leader",
        job_title="Team Leader",
        email=leader.email,
        status="Active",
        user_id=leader.id,
    )
    db.session.add(employee)
    db.session.flush()
    team = Team(
        team_name="Dashboard Installation Team",
        leader_employee_id=employee.id,
        status="Active",
    )
    db.session.add(team)
    db.session.flush()

    assigned = Project(
        project_name="Leader Assigned Project",
        customer_name="Assigned Customer",
        location="Berbera",
        project_type="Solar",
        status="Installation",
        created_by_id=admin.id,
    )
    outside = Project(
        project_name="Management Only Project",
        customer_name="Outside Customer",
        location="Burao",
        project_type="Solar",
        status="Survey",
        created_by_id=admin.id,
    )
    db.session.add_all([assigned, outside])
    db.session.flush()
    db.session.add(
        ProjectTeamAssignment(
            project_id=assigned.id,
            team_id=team.id,
            status="Active",
        )
    )
    db.session.commit()

    _login(client, leader)
    response = client.get("/dashboard")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "My assigned projects" in html
    assert "Leader Assigned Project" in html
    assert "Management Only Project" not in html
    assert "Financial Overview" not in html
    assert "Document Readiness" in html

    csv_response = client.get("/dashboard/export.csv")
    csv_text = csv_response.get_data(as_text=True)
    assert csv_response.status_code == 200
    assert "Leader Assigned Project" in csv_text
    assert "Management Only Project" not in csv_text
    assert "Revenue USD" not in csv_text
