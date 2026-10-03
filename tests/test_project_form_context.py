"""Phase 20J: project/customer context must follow project commands."""


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def _context_records():
    from app import db
    from app.models import Customer, Project, ProjectType, User
    from werkzeug.security import generate_password_hash

    user = User(
        full_name="Context Admin",
        email="context-admin@example.com",
        password_hash=generate_password_hash("Correct-Horse-Battery-1"),
        role="Admin",
        is_active=True,
    )
    customer = Customer(
        customer_name="Context Customer",
        phone="634445555",
        address="Hargeisa Main Road",
        is_active=True,
    )
    project_type = ProjectType(type_name="Hybrid Solar", is_active=True)
    db.session.add_all([user, customer, project_type])
    db.session.flush()
    project = Project(
        project_name="Context Solar Project",
        customer_name=customer.customer_name,
        location="Berbera Site",
        project_type=project_type.type_name,
        capacity="45 kWp",
        status="New",
        created_by_id=user.id,
    )
    db.session.add(project)
    db.session.commit()
    return user, customer, project


def test_project_command_links_and_quotation_defaults_keep_context(app, client):
    user, customer, project = _context_records()
    _login(client, user)

    project_page = client.get(f"/projects/{project.id}")
    project_html = project_page.get_data(as_text=True)
    assert project_page.status_code == 200
    assert "Project commands" in project_html
    assert f"/sales/quotations/create?project_id={project.id}" in project_html
    assert f"/materials/requests/create?project_id={project.id}" in project_html
    assert f"/payments/requests/create?project_id={project.id}" in project_html
    assert f"/support/tickets/create?project_id={project.id}" in project_html

    response = client.get(f"/sales/quotations/create?project_id={project.id}")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "data-customer='Context Customer'" in html
    assert "data-capacity='45 kWp'" in html
    assert "Context Customer" in html
    assert "selected>Context Solar Project - Context Customer</option>" in html

    post = client.post(
        "/sales/quotations/create",
        data={
            "project_id": str(project.id),
            "customer_name": "Wrong Customer",
            "project_type": project.project_type,
            "capacity": project.capacity,
            "validity_days": "15",
            "status": "Draft",
        },
        follow_redirects=False,
    )
    assert post.status_code == 302

    from app.models import SalesQuotation
    quotation = SalesQuotation.query.order_by(SalesQuotation.id.desc()).first()
    assert quotation.project_id == project.id
    assert quotation.customer_name == customer.customer_name


def test_service_and_warranty_forms_derive_customer_from_project(app, client):
    user, customer, project = _context_records()
    _login(client, user)

    ticket_form = client.get(f"/support/tickets/create?project_id={project.id}")
    ticket_html = ticket_form.get_data(as_text=True)
    assert ticket_form.status_code == 200
    assert f'value="{project.id}" data-customer-name="{customer.customer_name}"' in ticket_html
    assert "selected>Context Solar Project - Context Customer</option>" in ticket_html
    assert f'value="{customer.id}" data-phone="{customer.phone}"' in ticket_html

    ticket_post = client.post(
        "/support/tickets/create",
        data={
            "project_id": str(project.id),
            "new_customer_name": "Wrong Customer",
            "issue_description": "Inverter warning",
            "priority": "Medium",
            "status": "Open",
        },
        follow_redirects=False,
    )
    assert ticket_post.status_code == 302

    warranty_form = client.get(f"/support/warranties/create?project_id={project.id}")
    warranty_html = warranty_form.get_data(as_text=True)
    assert warranty_form.status_code == 200
    assert "value='Context Customer'" in warranty_html
    assert "value='45 kWp'" in warranty_html
    assert "selected>Context Solar Project - Context Customer</option>" in warranty_html

    warranty_post = client.post(
        "/support/warranties/create",
        data={
            "project_id": str(project.id),
            "customer_name": "Wrong Customer",
            "system_type": project.project_type,
            "capacity": project.capacity,
            "status": "Active",
        },
        follow_redirects=False,
    )
    assert warranty_post.status_code == 302

    from app.models import SupportTicket, WarrantyRegistration
    ticket = SupportTicket.query.order_by(SupportTicket.id.desc()).first()
    warranty = WarrantyRegistration.query.order_by(WarrantyRegistration.id.desc()).first()
    assert ticket.project_id == project.id
    assert ticket.customer_id == customer.id
    assert ticket.customer_name == customer.customer_name
    assert ticket.location == project.location
    assert warranty.project_id == project.id
    assert warranty.customer_id == customer.id
    assert warranty.customer_name == customer.customer_name
