from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.models import (
    Customer, Employee, Team, TeamMember, Project, ProjectTeamAssignment,
    ProjectEmployeeAssignment, Branch, Department, User, SalesInquiry,
    SalesQuotation, SupportTicket, WarrantyRegistration, WhatsAppMessage, Document,
    EMPLOYEE_STATUSES, EMPLOYEE_TYPES, TEAM_STATUSES, PROJECT_WORK_STATUSES
)
from app.permissions import can_manage_users, can_create_project

master_bp = Blueprint("master", __name__, url_prefix="/master")

def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()

def generate_employee_code():
    last = Employee.query.order_by(Employee.id.desc()).first()
    next_no = (last.id + 1) if last else 1
    return f"EMP-{next_no:04d}"

def require_manager():
    if can_manage_users(current_user) or can_create_project(current_user):
        return True
    flash("Only Admin, Management or Operation Manager can manage this section.", "danger")
    return False

@master_bp.route("/customers")
@login_required
def customers():
    q = (request.args.get("q") or "").strip()
    query = Customer.query
    if q:
        like = f"%{q}%"
        query = query.filter((Customer.customer_name.ilike(like)) | (Customer.phone.ilike(like)) | (Customer.contact_person.ilike(like)))
    customers = query.order_by(Customer.customer_name.asc()).all()
    return render_template("master/customers.html", customers=customers, q=q)



def _phone_suffix(phone):
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    return digits[-7:] if len(digits) >= 7 else digits

def _customer_360_context(customer):
    name = customer.customer_name
    phone_suffix = _phone_suffix(customer.phone)

    projects = Project.query.filter(Project.customer_name.ilike(name)).order_by(Project.created_at.desc()).limit(50).all()
    inquiries = SalesInquiry.query.filter(
        (SalesInquiry.customer_id == customer.id) | (SalesInquiry.customer_name.ilike(name))
    ).order_by(SalesInquiry.created_at.desc()).limit(20).all()
    quotations = SalesQuotation.query.filter(SalesQuotation.customer_name.ilike(name)).order_by(SalesQuotation.created_at.desc()).limit(50).all()
    tickets = SupportTicket.query.filter(
        (SupportTicket.customer_id == customer.id) | (SupportTicket.customer_name.ilike(name))
    ).order_by(SupportTicket.created_at.desc()).limit(20).all()
    warranties = WarrantyRegistration.query.filter(
        (WarrantyRegistration.customer_id == customer.id) | (WarrantyRegistration.customer_name.ilike(name))
    ).order_by(WarrantyRegistration.created_at.desc()).limit(20).all()

    whatsapp_query = WhatsAppMessage.query
    if phone_suffix:
        whatsapp_query = whatsapp_query.filter(WhatsAppMessage.phone_number.contains(phone_suffix))
    else:
        whatsapp_query = whatsapp_query.filter(WhatsAppMessage.recipient_name.ilike(name))
    whatsapp_messages = whatsapp_query.order_by(WhatsAppMessage.created_at.desc()).limit(30).all()

    project_ids = [p.id for p in projects]
    documents = Document.query.filter(Document.project_id.in_(project_ids)).order_by(Document.upload_date.desc()).limit(20).all() if project_ids else []

    total_quotation_value = sum(float(getattr(q, 'total_amount', 0) or 0) for q in quotations)
    open_quotations = [q for q in quotations if (q.status or '').lower() not in ['rejected', 'expired', 'converted to project']]
    open_projects = [p for p in projects if (p.status or '').lower() not in ['completed', 'cancelled', 'closed']]
    open_tickets = [t for t in tickets if (t.status or '').lower() not in ['resolved', 'closed', 'cancelled']]
    active_warranties = [w for w in warranties if (w.status or '').lower() == 'active']

    timeline = []
    def add_timeline(label, title, when, url=None, status=None):
        if when:
            timeline.append({'label': label, 'title': title, 'when': when, 'url': url, 'status': status})
    for q in quotations[:8]:
        add_timeline('Quotation', f'{q.ref_no} - {q.project_type or "Quotation"}', q.created_at, url_for('sales.quotation_detail', quotation_id=q.id), q.status)
    for p in projects[:8]:
        add_timeline('Project', p.project_name, p.created_at, url_for('projects.detail', project_id=p.id), p.status)
    for i in inquiries[:8]:
        add_timeline('Inquiry', f'{i.ref_no} - {i.project_type or "Inquiry"}', i.created_at, url_for('sales.inquiry_detail', inquiry_id=i.id), i.status)
    for t in tickets[:8]:
        add_timeline('Service', f'{t.ref_no} - {t.issue_category or "Ticket"}', t.created_at, url_for('support.ticket_detail', ticket_id=t.id), t.status)
    for m in whatsapp_messages[:8]:
        add_timeline('WhatsApp', (m.message_body or m.template_name or 'WhatsApp message')[:80], m.created_at, None, m.status)
    timeline = sorted(timeline, key=lambda x: x['when'], reverse=True)[:20]

    return {
        'projects': projects, 'inquiries': inquiries, 'quotations': quotations,
        'tickets': tickets, 'warranties': warranties, 'whatsapp_messages': whatsapp_messages,
        'documents': documents, 'timeline': timeline,
        'summary': {
            'quotation_count': len(quotations),
            'quotation_value': total_quotation_value,
            'open_quotations': len(open_quotations),
            'project_count': len(projects),
            'open_projects': len(open_projects),
            'ticket_count': len(tickets),
            'open_tickets': len(open_tickets),
            'active_warranties': len(active_warranties),
            'whatsapp_count': len(whatsapp_messages),
            'document_count': len(documents),
        },
        'phone_suffix': phone_suffix,
        'last_activity': timeline[0]['when'] if timeline else customer.created_at,
    }

@master_bp.route("/customers/create", methods=["GET", "POST"])
@login_required
def create_customer():
    if not require_manager(): return redirect(url_for("master.customers"))
    if request.method == "POST":
        name = request.form.get("customer_name", "").strip()
        if not name:
            flash("Customer name is required.", "danger")
            return redirect(url_for("master.create_customer"))
        if Customer.query.filter_by(customer_name=name).first():
            flash("Customer already exists.", "warning")
            return redirect(url_for("master.customers"))
        customer = Customer(
            customer_name=name,
            contact_person=request.form.get("contact_person"),
            phone=request.form.get("phone"),
            email=request.form.get("email"),
            address=request.form.get("address"),
            customer_type=request.form.get("customer_type"),
            remarks=request.form.get("remarks"),
            is_active=request.form.get("is_active") == "on",
        )
        db.session.add(customer)
        db.session.commit()
        flash("Customer created successfully.", "success")
        return redirect(url_for("master.customer_360", customer_id=customer.id))
    return render_template("master/customer_form.html", customer=None)


@master_bp.route("/customers/<int:customer_id>")
@login_required
def customer_360(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    context = _customer_360_context(customer)
    return render_template("master/customer_360.html", customer=customer, **context)

@master_bp.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    if not require_manager(): return redirect(url_for("master.customers"))
    customer = Customer.query.get_or_404(customer_id)
    old_name = customer.customer_name
    if request.method == "POST":
        new_name = request.form.get("customer_name", "").strip()
        if not new_name:
            flash("Customer name is required.", "danger")
            return redirect(url_for("master.edit_customer", customer_id=customer.id))
        duplicate = Customer.query.filter(Customer.customer_name == new_name, Customer.id != customer.id).first()
        if duplicate:
            flash("Another customer with this name already exists.", "danger")
            return redirect(url_for("master.edit_customer", customer_id=customer.id))
        customer.customer_name = new_name
        customer.contact_person = request.form.get("contact_person")
        customer.phone = request.form.get("phone")
        customer.email = request.form.get("email")
        customer.address = request.form.get("address")
        customer.customer_type = request.form.get("customer_type")
        customer.remarks = request.form.get("remarks")
        customer.is_active = request.form.get("is_active") == "on"
        if old_name != new_name:
            Project.query.filter_by(customer_name=old_name).update({"customer_name": new_name})
        db.session.commit()
        flash("Customer updated successfully.", "success")
        return redirect(url_for("master.customer_360", customer_id=customer.id))
    return render_template("master/customer_form.html", customer=customer)

@master_bp.route("/employees")
@login_required
def employees():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    query = Employee.query
    if q:
        like = f"%{q}%"
        query = query.filter((Employee.full_name.ilike(like)) | (Employee.employee_code.ilike(like)) | (Employee.job_title.ilike(like)))
    if status:
        query = query.filter(Employee.status == status)
    employees = query.order_by(Employee.full_name.asc()).all()
    return render_template("master/employees.html", employees=employees, q=q, status=status, statuses=EMPLOYEE_STATUSES)

@master_bp.route("/employees/create", methods=["GET", "POST"])
@login_required
def create_employee():
    if not require_manager(): return redirect(url_for("master.employees"))
    if request.method == "POST":
        employee = Employee(
            employee_code=generate_employee_code(),
            full_name=request.form.get("full_name"),
            job_title=request.form.get("job_title"),
            phone=request.form.get("phone"),
            email=request.form.get("email"),
            employee_type=request.form.get("employee_type"),
            status=request.form.get("status"),
            branch_id=request.form.get("branch_id") or None,
            department_id=request.form.get("department_id") or None,
            user_id=request.form.get("user_id") or None,
            remarks=request.form.get("remarks"),
        )
        db.session.add(employee)
        db.session.commit()
        flash("Employee created successfully.", "success")
        return redirect(url_for("master.employees"))
    return render_template("master/employee_form.html", employee=None, branches=Branch.query.all(), departments=Department.query.all(), users=User.query.all(), statuses=EMPLOYEE_STATUSES, types=EMPLOYEE_TYPES)

@master_bp.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
def edit_employee(employee_id):
    if not require_manager(): return redirect(url_for("master.employees"))
    employee = Employee.query.get_or_404(employee_id)
    if request.method == "POST":
        employee.employee_code = request.form.get("employee_code") or None
        employee.full_name = request.form.get("full_name")
        employee.job_title = request.form.get("job_title")
        employee.phone = request.form.get("phone")
        employee.email = request.form.get("email")
        employee.employee_type = request.form.get("employee_type")
        employee.status = request.form.get("status")
        employee.branch_id = request.form.get("branch_id") or None
        employee.department_id = request.form.get("department_id") or None
        employee.user_id = request.form.get("user_id") or None
        employee.remarks = request.form.get("remarks")
        db.session.commit()
        flash("Employee updated successfully.", "success")
        return redirect(url_for("master.employees"))
    return render_template("master/employee_form.html", employee=employee, branches=Branch.query.all(), departments=Department.query.all(), users=User.query.all(), statuses=EMPLOYEE_STATUSES, types=EMPLOYEE_TYPES)

@master_bp.route("/teams")
@login_required
def teams():
    q = (request.args.get("q") or "").strip()
    query = Team.query
    if q:
        like = f"%{q}%"
        query = query.filter((Team.team_name.ilike(like)) | (Team.team_type.ilike(like)))
    teams = query.order_by(Team.team_name.asc()).all()
    return render_template("master/teams.html", teams=teams, q=q)

@master_bp.route("/teams/create", methods=["GET", "POST"])
@login_required
def create_team():
    if not require_manager(): return redirect(url_for("master.teams"))
    employees = Employee.query.filter_by(status="Active").order_by(Employee.full_name.asc()).all()
    if request.method == "POST":
        team = Team(
            team_name=request.form.get("team_name"),
            team_type=request.form.get("team_type"),
            leader_employee_id=request.form.get("leader_employee_id") or None,
            branch_id=request.form.get("branch_id") or None,
            department_id=request.form.get("department_id") or None,
            status=request.form.get("status"),
            remarks=request.form.get("remarks"),
        )
        db.session.add(team)
        db.session.commit()
        flash("Team created successfully. You can now add members.", "success")
        return redirect(url_for("master.team_detail", team_id=team.id))
    return render_template("master/team_form.html", team=None, employees=employees, branches=Branch.query.all(), departments=Department.query.all(), statuses=TEAM_STATUSES)

@master_bp.route("/teams/<int:team_id>")
@login_required
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    employees = Employee.query.filter_by(status="Active").order_by(Employee.full_name.asc()).all()
    return render_template("master/team_detail.html", team=team, employees=employees)

@master_bp.route("/teams/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
def edit_team(team_id):
    if not require_manager(): return redirect(url_for("master.teams"))
    team = Team.query.get_or_404(team_id)
    employees = Employee.query.filter_by(status="Active").order_by(Employee.full_name.asc()).all()
    if request.method == "POST":
        team.team_name = request.form.get("team_name")
        team.team_type = request.form.get("team_type")
        team.leader_employee_id = request.form.get("leader_employee_id") or None
        team.branch_id = request.form.get("branch_id") or None
        team.department_id = request.form.get("department_id") or None
        team.status = request.form.get("status")
        team.remarks = request.form.get("remarks")
        db.session.commit()
        flash("Team updated successfully.", "success")
        return redirect(url_for("master.team_detail", team_id=team.id))
    return render_template("master/team_form.html", team=team, employees=employees, branches=Branch.query.all(), departments=Department.query.all(), statuses=TEAM_STATUSES)

@master_bp.route("/teams/<int:team_id>/members/add", methods=["POST"])
@login_required
def add_team_member(team_id):
    if not require_manager(): return redirect(url_for("master.team_detail", team_id=team_id))
    employee_id = request.form.get("employee_id")
    if not employee_id:
        flash("Select employee.", "danger")
        return redirect(url_for("master.team_detail", team_id=team_id))
    existing = TeamMember.query.filter_by(team_id=team_id, employee_id=employee_id, is_active=True).first()
    if existing:
        flash("Employee is already active in this team.", "warning")
    else:
        db.session.add(TeamMember(team_id=team_id, employee_id=employee_id, member_role=request.form.get("member_role"), is_active=True))
        db.session.commit()
        flash("Team member added.", "success")
    return redirect(url_for("master.team_detail", team_id=team_id))

@master_bp.route("/teams/<int:team_id>/members/<int:member_id>/remove")
@login_required
def remove_team_member(team_id, member_id):
    if not require_manager(): return redirect(url_for("master.team_detail", team_id=team_id))
    member = TeamMember.query.get_or_404(member_id)
    member.is_active = False
    db.session.commit()
    flash("Team member removed from active list.", "success")
    return redirect(url_for("master.team_detail", team_id=team_id))

@master_bp.route("/projects/<int:project_id>/workforce", methods=["GET", "POST"])
@login_required
def project_workforce(project_id):
    if not require_manager(): return redirect(url_for("projects.detail", project_id=project_id))
    project = Project.query.get_or_404(project_id)
    teams = Team.query.filter_by(status="Active").order_by(Team.team_name.asc()).all()
    employees = Employee.query.filter_by(status="Active").order_by(Employee.full_name.asc()).all()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_team":
            team_id = request.form.get("team_id")
            if team_id:
                db.session.add(ProjectTeamAssignment(
                    project_id=project.id,
                    team_id=team_id,
                    work_scope=request.form.get("work_scope"),
                    start_date=parse_date(request.form.get("start_date")),
                    end_date=parse_date(request.form.get("end_date")),
                    status=request.form.get("status") or "Active",
                    remarks=request.form.get("remarks"),
                ))
                db.session.commit()
                flash("Team assigned to project.", "success")
        elif action == "add_employee":
            employee_id = request.form.get("employee_id")
            if employee_id:
                db.session.add(ProjectEmployeeAssignment(
                    project_id=project.id,
                    employee_id=employee_id,
                    role_on_project=request.form.get("role_on_project"),
                    work_scope=request.form.get("work_scope"),
                    start_date=parse_date(request.form.get("start_date")),
                    end_date=parse_date(request.form.get("end_date")),
                    status=request.form.get("status") or "Active",
                    remarks=request.form.get("remarks"),
                ))
                db.session.commit()
                flash("Employee assigned to project.", "success")
        return redirect(url_for("master.project_workforce", project_id=project.id))

    return render_template("master/project_workforce.html", project=project, teams=teams, employees=employees, work_statuses=PROJECT_WORK_STATUSES)

@master_bp.route("/projects/<int:project_id>/workforce/team/<int:assignment_id>/remove")
@login_required
def remove_project_team(project_id, assignment_id):
    if not require_manager(): return redirect(url_for("projects.detail", project_id=project_id))
    assignment = ProjectTeamAssignment.query.get_or_404(assignment_id)
    assignment.status = "Removed"
    db.session.commit()
    flash("Project team assignment removed.", "success")
    return redirect(url_for("master.project_workforce", project_id=project_id))

@master_bp.route("/projects/<int:project_id>/workforce/employee/<int:assignment_id>/remove")
@login_required
def remove_project_employee(project_id, assignment_id):
    if not require_manager(): return redirect(url_for("projects.detail", project_id=project_id))
    assignment = ProjectEmployeeAssignment.query.get_or_404(assignment_id)
    assignment.status = "Removed"
    db.session.commit()
    flash("Project employee assignment removed.", "success")
    return redirect(url_for("master.project_workforce", project_id=project_id))