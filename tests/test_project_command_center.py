from datetime import date, timedelta


def test_command_center_uses_operational_records_and_renders(app, client):
    from app import db
    from app.models import (
        DailySiteReport,
        MaterialRequest,
        PaymentRequest,
        Project,
        ProjectTask,
        SalesQuotation,
        SalesQuotationLine,
        SiteSurveyForm,
        User,
    )
    from app.project_command_center import build_project_command_center
    from werkzeug.security import generate_password_hash

    today = date(2026, 7, 28)
    user = User(
        full_name="Command Center Admin",
        email="command@example.com",
        password_hash=generate_password_hash("Correct-Horse-Battery-1"),
        role="Admin",
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()

    project = Project(
        project_name="North Clinic Solar",
        customer_name="North Clinic",
        location="Hargeisa",
        project_type="Hybrid Solar",
        capacity="30 kWp",
        start_date=today - timedelta(days=30),
        expected_completion_date=today + timedelta(days=30),
        status="Installation",
        created_by_id=user.id,
    )
    db.session.add(project)
    db.session.flush()
    db.session.add_all([
        ProjectTask(
            project_id=project.id,
            title="Install PV modules",
            created_by_id=user.id,
            status="In Progress",
            progress_percent=50,
            start_date=today - timedelta(days=5),
            due_date=today + timedelta(days=5),
        ),
        DailySiteReport(
            project_id=project.id,
            created_by_id=user.id,
            report_date=today,
            progress_percentage="60%",
            work_done_today="Mounted the first array.",
            approval_status="Approved",
        ),
        SiteSurveyForm(
            project_id=project.id,
            created_by_id=user.id,
            survey_date=today - timedelta(days=25),
            approval_status="Approved",
        ),
        MaterialRequest(
            ref_no="MRF-COMMAND-1",
            project_id=project.id,
            request_date=today,
            purpose="PV installation",
            status="Approved",
            requested_by_id=user.id,
        ),
    ])
    quotation = SalesQuotation(
        ref_no="QTN-COMMAND-1",
        project_id=project.id,
        quotation_date=today,
        customer_name=project.customer_name,
        status="Approved by Customer",
        prepared_by_id=user.id,
    )
    db.session.add(quotation)
    db.session.flush()
    db.session.add(SalesQuotationLine(
        quotation_id=quotation.id,
        item="Solar project",
        quantity=1,
        unit_price=10000,
    ))
    db.session.add(PaymentRequest(
        request_no="PR-COMMAND-1",
        requested_by_id=user.id,
        project_id=project.id,
        payee_name="Site contractor",
        category="Project Expense",
        purpose="Installation labour",
        amount=2000,
        currency="USD",
        status="Approved",
    ))
    db.session.commit()

    snapshot = build_project_command_center(project, today=today)
    assert snapshot["physical"]["progress"] == 56
    assert snapshot["procurement"]["progress"] == 55
    # The approved survey and approved daily report complete two of the seven
    # required form gates: 2 / 7 = 29% readiness.
    assert snapshot["documents"]["progress"] == 29
    assert snapshot["overall"] == 49
    assert snapshot["financials"]["revenue"] == 10000
    assert snapshot["financials"]["committed_cost"] == 2000
    assert snapshot["financials"]["profit"] == 8000

    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    response = client.get(f"/projects/{project.id}")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Project Command Center" in html
    assert "Timeline / Gantt view" in html
    assert "Financial progress" in html
    assert "AI project summary" in html
    assert "North Clinic Solar" in html
