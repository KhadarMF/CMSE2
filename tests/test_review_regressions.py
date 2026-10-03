"""End-to-end regressions for the ERP review repairs."""
import io
from datetime import date

import pytest


@pytest.fixture(autouse=True)
def disable_outbound_email(monkeypatch):
    monkeypatch.setattr("app.notifications.send_email", lambda *args, **kwargs: None)


def login(client, user):
    from flask import g
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    g.pop("_login_user", None)


def setup_project():
    from app import db
    from app.models import User, Project
    user = User(full_name="Review Admin", email="review@example.invalid", role="Admin", password_hash="unused", is_active=True)
    db.session.add(user)
    db.session.flush()
    project = Project(project_name="Review Pump", customer_name="Review Customer", location="Test Site", project_type="Solar Pumping", created_by_id=user.id)
    db.session.add(project)
    db.session.commit()
    return user, project


def test_survey_permissions_can_be_saved_and_used(app, client):
    from app import db
    from app.models import User, UserFormPermission
    admin, project = setup_project()
    engineer = User(full_name="Engineer", email="engineer@example.invalid", role="Technical Engineer", password_hash="unused", is_active=True)
    db.session.add(engineer)
    db.session.commit()
    login(client, admin)
    response = client.post(f"/admin/form-permissions?user_id={engineer.id}", data={"user_id": engineer.id, "solar-pump-survey_view": "on", "solar-pump-survey_create": "on", "solar-pump-survey_edit": "on"})
    assert response.status_code == 302
    assert UserFormPermission.query.filter_by(user_id=engineer.id, form_key="solar-pump-survey").one().can_create
    login(client, engineer)
    assert client.get("/forms/").status_code == 200
    assert client.get(f"/forms/solar-pump-survey/new?project_id={project.id}").status_code == 200


def test_survey_crud_duplicate_guards_and_approval_reset(app, client):
    from app import db
    from app.models import Project, SolarPumpSurveyForm, ApprovalHistory
    user, project = setup_project()
    second = Project(project_name="Second", customer_name="Review Customer", location="Test", project_type="Solar Pumping", created_by_id=user.id)
    db.session.add(second)
    db.session.commit()
    login(client, user)
    for p in (project, second):
        assert client.post("/forms/solar-pump-survey/new", data={"project_id": p.id, "survey_date": "2026-09-12", "water_source": "Borehole", "approval_status": "Draft"}).status_code == 302
    entry = SolarPumpSurveyForm.query.filter_by(project_id=project.id).one()
    assert client.post("/forms/solar-pump-survey/new", data={"project_id": project.id}).status_code == 302
    assert SolarPumpSurveyForm.query.count() == 2
    client.post(f"/forms/solar-pump-survey/{entry.id}/edit", data={"project_id": second.id})
    db.session.refresh(entry)
    assert entry.project_id == project.id
    entry.approval_status = "Approved"
    entry.reviewed_by_id = user.id
    db.session.commit()
    client.post(f"/forms/solar-pump-survey/{entry.id}/edit", data={"project_id": project.id, "required_flow_m3h": "12.5"})
    db.session.refresh(entry)
    assert entry.approval_status == "Draft"
    assert entry.reviewed_by_id is None and entry.required_flow_m3h == "12.5"
    assert ApprovalHistory.query.filter_by(record_id=entry.id, previous_status="Approved", new_status="Draft").count() == 1


def test_forms_reject_approval_injection_and_invalid_project_dates(app, client):
    from app.models import SiteSurveyForm, SolarPumpSurveyForm
    user, project = setup_project()
    login(client, user)
    for key, model in [("site-survey", SiteSurveyForm), ("solar-pump-survey", SolarPumpSurveyForm)]:
        for invalid in [dict(approval_status="Approved"), dict(project_id="999999"), dict(project_id="bad"), dict(survey_date="not-a-date")]:
            payload = {"project_id": project.id, **invalid}
            response = client.post(f"/forms/{key}/new", data=payload)
            assert response.status_code == 302
            assert model.query.count() == 0


def test_pumping_evidence_is_counted_and_legacy_load_is_not_required(app, client):
    from app import db
    from app.models import SolarPumpSurveyForm, ProjectTask
    from app.milestone_service import ensure_default_milestones, build_milestone_snapshot
    from app.project_command_center import build_project_command_center
    from app.dashboard_command_center import _form_counts
    from app.routes.report_routes import project_checklist, project_report_data, build_customer_summary
    user, project = setup_project()
    ensure_default_milestones(project, user.id)
    survey = next(m for m in project.milestones if m.code == "SURVEY")
    assert survey.document_requirements[0].form_key == "solar-pump-survey"
    db.session.add_all([
        SolarPumpSurveyForm(project_id=project.id, created_by_id=user.id, approval_status="Approved"),
        ProjectTask(project_id=project.id, milestone_id=survey.id, title="Survey visit", status="Completed", progress_percent=100, created_by_id=user.id),
    ])
    db.session.commit()
    assert build_milestone_snapshot(survey)["ready"]
    checklist, _ = project_checklist(project)
    assert checklist[0]["status"] == "Approved"
    assert all("Load Assessment" not in item["label"] for item in checklist)
    assert project_report_data(project)["summary"]["approved_forms"] == 1
    assert build_customer_summary([project])[0]["forms"] == 1
    assert _form_counts([project.id])["approved"] == 1
    login(client, user)
    html = client.get(f"/projects/{project.id}").get_data(as_text=True)
    assert "solar-pump-survey" in html


def test_upgrade_repairs_only_unlinked_default_pumping_requirement(app):
    from app import db
    from app.models import MilestoneDocumentRequirement
    from app.milestone_service import ensure_default_milestones
    from flask_migrate import downgrade, upgrade
    user, project = setup_project()
    ensure_default_milestones(project, user.id)
    survey = next(m for m in project.milestones if m.code == "SURVEY")
    requirement = survey.document_requirements[0]
    requirement.form_key = "site-survey"
    requirement.title = "Approved site survey & load assessment"
    custom = MilestoneDocumentRequirement(milestone_id=survey.id, title="Custom historic survey", form_key="site-survey", form_record_id=7)
    db.session.add(custom)
    db.session.commit()
    downgrade(revision="b20k0000a001")
    upgrade()
    db.session.expire_all()
    assert requirement.form_key == "solar-pump-survey"
    assert custom.form_key == "site-survey" and custom.form_record_id == 7


def test_legacy_survey_values_and_history_remain_visible(app, client):
    from app import db
    from app.models import SiteSurveyForm, ApprovalHistory
    user, project = setup_project()
    entry = SiteSurveyForm(project_id=project.id, created_by_id=user.id, daytime_load_kw="47", pump_loads="Legacy pump measurement")
    db.session.add(entry)
    db.session.flush()
    db.session.add(ApprovalHistory(module="Site Survey & Load Assessment", record_id=entry.id, previous_status="Submitted", new_status="Approved", comments="Historical approval note", reviewed_by_id=user.id))
    db.session.commit()
    login(client, user)
    html = client.get(f"/forms/site-survey/{entry.id}").get_data(as_text=True)
    assert "47" in html and "Legacy pump measurement" in html and "Historical approval note" in html


def test_payment_amount_validation_and_last_cent(app, client):
    from app import db
    from app.models import PaymentRequest, PaymentRequestPayment
    user, _ = setup_project()
    pr = PaymentRequest(request_no="REVIEW-PR", requested_by_id=user.id, payee_name="Vendor", purpose="Test payment", amount=100, currency="USD", status="Approved")
    db.session.add(pr)
    db.session.commit()
    login(client, user)
    url = f"/payments/requests/{pr.id}/payment"
    for value in ("nan", "inf", "1e999", "-1", "0.001", "100.01"):
        assert client.post(url, data={"amount": value}).status_code == 302
        assert PaymentRequestPayment.query.count() == 0
    client.post(url, data={"amount": "99.99"})
    db.session.refresh(pr)
    assert pr.status == "Partially Paid" and round(pr.balance, 2) == .01
    client.post(url, data={"amount": "0.005"})
    db.session.refresh(pr)
    assert pr.status == "Paid" and round(pr.balance, 2) == 0
    assert PaymentRequestPayment.query.count() == 2


def test_payroll_requires_approval_and_cannot_overpay(app, client):
    from app import db
    from app.models import Employee, ProjectPayrollBatch, ProjectPayrollEntry, ProjectPayrollPayment
    user, project = setup_project()
    employee = Employee(employee_code="REVIEW-EMP", full_name="Worker", status="Active")
    batch = ProjectPayrollBatch(batch_no="REVIEW-BATCH", batch_title="Test payroll", project_id=project.id, created_by_id=user.id, status="Submitted")
    db.session.add_all([employee, batch])
    db.session.flush()
    entry = ProjectPayrollEntry(batch_id=batch.id, employee_id=employee.id, project_amount=100, status="Pending")
    db.session.add(entry)
    db.session.commit()
    login(client, user)
    url = f"/payroll/entries/{entry.id}/payment"
    client.post(url, data={"amount": "100"})
    assert ProjectPayrollPayment.query.count() == 0
    assert client.get(f"/payroll/batches/{batch.id}/approve").status_code == 405
    client.post(f"/payroll/batches/{batch.id}/approve")
    for value in ("100.01", "NaN", "Infinity"):
        client.post(url, data={"amount": value})
        assert ProjectPayrollPayment.query.count() == 0
    client.post(url, data={"amount": "100"})
    db.session.refresh(entry)
    db.session.refresh(batch)
    assert entry.status == "Paid" and batch.status == "Paid"
    assert round(entry.balance, 2) == 0


def test_document_approval_injection_and_upload_collision(app, client):
    from app.models import Document
    user, project = setup_project()
    login(client, user)
    def upload(status):
        return client.post("/documents/upload", data={"project_id": project.id, "document_title": "Evidence", "document_type": "Technical Design", "approval_status": status, "file": (io.BytesIO(b"test file"), "same.txt.pdf")})
    upload("Approved")
    assert Document.query.count() == 0
    upload("Submitted")
    upload("Submitted")
    docs = Document.query.all()
    assert len(docs) == 2 and docs[0].stored_file_name != docs[1].stored_file_name
    client.post(f"/documents/{docs[0].id}/review", data={"approval_status": "Approved"})
    assert docs[0].approval_status == "Submitted"


def test_inactive_and_malformed_sessions_are_rejected(app, client):
    from app import db
    from flask import g
    user, _ = setup_project()
    login(client, user)
    user.is_active = False
    db.session.commit()
    g.pop("_login_user", None)
    response = client.get("/projects/")
    assert response.status_code == 302 and "/login" in response.location
    with client.session_transaction() as session:
        session["_user_id"] = "bad-id"
    g.pop("_login_user", None)
    response = client.get("/projects/")
    assert response.status_code == 302 and "/login" in response.location


def test_read_only_permission_cannot_approve_payment_or_export_other_form(app, client):
    from app import db
    from app.models import User, UserFormPermission, PaymentRequest
    user, project = setup_project()
    manager = User(full_name="Read Only Manager", email="readonly@example.invalid", role="Management", password_hash="unused", is_active=True)
    db.session.add(manager)
    db.session.flush()
    db.session.add_all([UserFormPermission(user_id=manager.id, form_key="payment-requests", can_view=True), UserFormPermission(user_id=manager.id, form_key="form-reports", can_print_export=True)])
    pr = PaymentRequest(request_no="READ-ONLY", requested_by_id=user.id, payee_name="Vendor", purpose="Example", amount=5, status="Pending Manager Approval")
    db.session.add(pr)
    db.session.commit()
    login(client, manager)
    client.post(f"/payments/requests/{pr.id}/reject", data={"reason": "Must not succeed"})
    assert pr.status == "Pending Manager Approval"
    response = client.get("/reports/form/solar-pump-survey/1/pdf")
    assert response.status_code == 302 and "dashboard" in response.location


def test_mutating_routes_require_post_and_csrf(csrf_app):
    endpoints = {"payroll.approve_batch", "admin.toggle_branch", "admin.toggle_department", "users.toggle_user", "master.remove_team_member", "master.remove_project_team", "master.remove_project_employee", "notifications.send_email_log", "notifications.mark_sms_sent", "notifications.mark_read"}
    for rule in csrf_app.url_map.iter_rules():
        if rule.endpoint in endpoints:
            assert "POST" in rule.methods and "GET" not in rule.methods
    response = csrf_app.test_client().post("/payroll/batches/1/approve")
    assert response.status_code == 400


def test_common_pages_render_and_new_projects_cannot_skip_completion(app, client):
    user, project = setup_project()
    login(client, user)
    paths = ["/dashboard", "/projects/", f"/projects/{project.id}", "/forms/", "/forms/site-survey/new", "/forms/solar-pump-survey/new", "/documents/", "/documents/upload", "/accounting/", "/payments/", "/payroll/", "/payroll/batches/create", "/materials/", "/users/", "/admin/form-permissions", "/reports/", f"/reports/project/{project.id}/full"]
    for path in paths:
        assert client.get(path).status_code == 200, path
    from app.models import Project
    client.post("/projects/create", data={"project_name": "Bypass", "customer_name": "Test", "location": "Test", "project_type": "Solar Pumping", "status": "Completed"})
    assert Project.query.filter_by(project_name="Bypass").count() == 0


def test_editing_evidence_reopens_completed_milestone(app, client):
    from app import db
    from app.models import SolarPumpSurveyForm
    from app.milestone_service import ensure_default_milestones
    user, project = setup_project()
    ensure_default_milestones(project, user.id)
    survey = next(m for m in project.milestones if m.code == "SURVEY")
    survey.status = "Completed"
    project.status = "Completed"
    entry = SolarPumpSurveyForm(project_id=project.id, created_by_id=user.id, approval_status="Approved")
    db.session.add(entry)
    db.session.commit()
    login(client, user)
    client.post(f"/forms/solar-pump-survey/{entry.id}/edit", data={"project_id": project.id, "water_source": "Updated borehole"})
    db.session.refresh(survey)
    db.session.refresh(project)
    assert survey.status == "In Progress" and project.status == "Handover"
    assert any(log.action == "Reopen" for log in survey.audit_logs)


def test_bootstrap_migrates_and_never_resets_an_existing_admin(app, monkeypatch, capsys):
    from app.models import User, ProjectType
    from werkzeug.security import check_password_hash
    from init_db import initialize_database
    password = "Only-for-automated-test-1234"
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "bootstrap@example.invalid")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", password)
    initialize_database(app)
    admin = User.query.filter_by(email="bootstrap@example.invalid").one()
    assert check_password_hash(admin.password_hash, password)
    assert ProjectType.query.filter_by(type_name="Solar Pump System").count() == 1
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "replacement-must-not-be-applied")
    initialize_database(app)
    assert User.query.count() == 1 and check_password_hash(admin.password_hash, password)
    capsys.readouterr()


def test_local_environment_setup_generates_private_secret(tmp_path, monkeypatch):
    import app.local_setup as setup
    from dotenv import dotenv_values
    monkeypatch.setattr(setup, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("RENDER", raising=False)
    setup.prepare_local_environment()
    first = dotenv_values(tmp_path / ".env")
    assert len(first["SECRET_KEY"]) >= 32 and first["SESSION_COOKIE_SECURE"] == "0"
    setup.prepare_local_environment()
    assert dotenv_values(tmp_path / ".env")["SECRET_KEY"] == first["SECRET_KEY"]


def test_process_database_configuration_takes_precedence(app, tmp_path, monkeypatch):
    import app as module
    from app import db
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///wrong-database.db\nSECRET_KEY=wrong-secret\n", encoding="utf-8")
    monkeypatch.setattr(module, "__file__", str(tmp_path / "app" / "__init__.py"))
    other = module.create_app()
    assert other.config["SQLALCHEMY_DATABASE_URI"] == app.config["SQLALCHEMY_DATABASE_URI"]
    assert other.config["SECRET_KEY"] != "wrong-secret"
    with other.app_context():
        db.engine.dispose()


def test_numeric_types_reject_nonfinite_values():
    from app.types import Money, Quantity, Rate
    for kind in (Money, Quantity, Rate):
        for value in ("NaN", "Infinity", "-Infinity", "invalid"):
            with pytest.raises(ValueError):
                kind().process_bind_param(value, None)


def test_simultaneous_requests_do_not_overpay_or_duplicate_forms(app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app import db
    from app.models import PaymentRequest, PaymentRequestPayment, SiteSurveyForm
    user, project = setup_project()
    user_id, project_id = user.id, project.id
    payment_request = PaymentRequest(request_no="CONCURRENT-PR", requested_by_id=user_id, payee_name="Vendor", purpose="Concurrency check", amount=100, status="Approved", currency="USD")
    db.session.add(payment_request)
    db.session.commit()
    request_id = payment_request.id

    def together(url, payload):
        barrier = Barrier(2)
        def post():
            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True
            barrier.wait(timeout=10)
            return client.post(url, data=payload).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(post) for _ in range(2)]
            assert [future.result(timeout=30) for future in futures] == [302, 302]

    together(f"/payments/requests/{request_id}/payment", {"amount": "75"})
    assert PaymentRequestPayment.query.count() == 1
    together("/forms/site-survey/new", {"project_id": project_id, "approval_status": "Draft"})
    assert SiteSurveyForm.query.count() == 1


def test_native_survey_export_returns_pdf_or_printable_fallback(app, client):
    from app import db
    from app.models import SolarPumpSurveyForm
    user, project = setup_project()
    entry = SolarPumpSurveyForm(project_id=project.id, created_by_id=user.id, water_source="Borehole", required_flow_m3h="12.5")
    db.session.add(entry)
    db.session.commit()
    login(client, user)
    response = client.get(f"/reports/form/solar-pump-survey/{entry.id}/pdf")
    assert response.status_code == 200
    if response.mimetype == "application/pdf":
        assert response.data.startswith(b"%PDF-") and b"%%EOF" in response.data[-50:]
    else:
        assert response.headers["X-PDF-Fallback"] == "printable-html"
        assert b"Print / Save as PDF" in response.data and b"Borehole" in response.data
    assert client.get("/dashboard").status_code == 200


def test_project_edit_permission_does_not_require_create_permission(app, client):
    from app import db
    from app.models import User, UserFormPermission
    _, project = setup_project()
    editor = User(full_name="Project Editor", email="editor@example.invalid", role="Technical Engineer", password_hash="unused", is_active=True)
    db.session.add(editor)
    db.session.flush()
    db.session.add(UserFormPermission(user_id=editor.id, form_key="projects", can_view=True, can_edit=True, can_create=False))
    db.session.commit()
    login(client, editor)
    assert client.get(f"/projects/{project.id}/edit").status_code == 200


def test_pdf_worker_failures_and_success_are_handled(monkeypatch):
    import subprocess
    from types import SimpleNamespace
    from app.pdf_service import render_pdf, PDFRenderError
    import app.pdf_service as service
    monkeypatch.setattr(service.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=b"%PDF-test", stderr=b""))
    assert render_pdf("<html>Report</html>", "http://localhost/") == b"%PDF-test"
    monkeypatch.setattr(service.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout=b"", stderr=b"native renderer failed"))
    with pytest.raises(PDFRenderError):
        render_pdf("<html>Report</html>", "http://localhost/")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("pdf_worker", 45)
    monkeypatch.setattr(service.subprocess, "run", timeout)
    with pytest.raises(PDFRenderError):
        render_pdf("<html>Report</html>", "http://localhost/")
