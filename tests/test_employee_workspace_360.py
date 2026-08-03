from datetime import date, timedelta


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def _admin_and_employee():
    from app import db
    from app.models import Employee, User
    from werkzeug.security import generate_password_hash

    admin = User(
        full_name="Employee Workspace Admin",
        email="employee-workspace@example.com",
        password_hash=generate_password_hash("Correct-Horse-Battery-1"),
        role="Admin",
        is_active=True,
    )
    employee = Employee(
        employee_code="EMP-360-001",
        full_name="Amina Hassan",
        job_title="Solar Technician",
        phone="+252 63 0000000",
        email="amina@example.com",
        employee_type="Full-time",
        status="Active",
    )
    db.session.add_all([admin, employee])
    db.session.commit()
    return admin, employee


def test_employee_workspace_360_renders_profile_tabs_and_actions(app, client):
    admin, employee = _admin_and_employee()
    _login(client, admin)

    response = client.get(f"/master/employees/{employee.id}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Employee Workspace 360" in html
    assert "Amina Hassan" in html
    assert "EMP-360-001" in html
    assert "Projects" in html
    assert "Teams" in html
    assert "Tasks" in html
    assert "Payroll" in html
    assert "Service" in html
    assert "Timeline" in html
    assert f'/master/employees/{employee.id}/delete' in html


def test_unused_employee_can_be_deleted(app, client):
    from app import db
    from app.models import Employee

    admin, employee = _admin_and_employee()
    employee_id = employee.id
    _login(client, admin)

    response = client.post(
        f"/master/employees/{employee_id}/delete",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "deleted successfully" in response.get_data(as_text=True)
    assert db.session.get(Employee, employee_id) is None


def test_employee_with_operational_history_cannot_be_deleted(app, client):
    from app import db
    from app.models import Employee, Project, ProjectTask

    admin, employee = _admin_and_employee()
    project = Project(
        project_name="Employee 360 Solar Site",
        customer_name="Demo Customer",
        location="Hargeisa",
        project_type="Hybrid Solar",
        status="Installation",
        created_by_id=admin.id,
    )
    db.session.add(project)
    db.session.flush()
    db.session.add(ProjectTask(
        project_id=project.id,
        title="Install inverter protection",
        assigned_employee_id=employee.id,
        created_by_id=admin.id,
        status="In Progress",
        priority="High",
        progress_percent=40,
        start_date=date.today() - timedelta(days=2),
        due_date=date.today() + timedelta(days=3),
    ))
    db.session.commit()
    employee_id = employee.id
    _login(client, admin)

    response = client.post(
        f"/master/employees/{employee_id}/delete",
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "cannot be permanently deleted" in html
    assert "Project tasks: 1" in html
    assert "Inactive" in html
    assert db.session.get(Employee, employee_id) is not None
