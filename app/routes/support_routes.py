from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from app import db
from app.notification_gateway import create_notification_event
from app.models import (
    Customer, Project, Employee, User, WarrantyRegistration, SupportTicket, ServiceVisit,
    WARRANTY_STATUSES, TICKET_STATUSES, TICKET_PRIORITIES, VISIT_STATUSES,
    TICKET_CATEGORIES, COMPLAINT_SOURCES, SERVICE_RESULTS, CUSTOMER_CONFIRMATIONS
)

support_bp = Blueprint('support', __name__, url_prefix='/support')

def parse_date(v):
    if not v:
        return None
    try:
        return datetime.strptime(v, '%Y-%m-%d').date()
    except Exception:
        return None

def make_ref(prefix):
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

@support_bp.before_app_request
def ensure_support_tables():
    try:
        db.create_all()
    except Exception:
        pass

@support_bp.route('/')
@login_required
def dashboard():
    tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).limit(10).all()
    warranties = WarrantyRegistration.query.order_by(WarrantyRegistration.created_at.desc()).limit(10).all()
    open_statuses = ['Open', 'Assigned', 'In Progress', 'Waiting Parts', 'Pending Customer']
    today = date.today()
    summary = {
        'tickets': SupportTicket.query.count(),
        'open': SupportTicket.query.filter(SupportTicket.status.in_(open_statuses)).count(),
        'urgent': SupportTicket.query.filter_by(priority='Urgent').count(),
        'waiting_parts': SupportTicket.query.filter_by(status='Waiting Parts').count(),
        'overdue': SupportTicket.query.filter(SupportTicket.status.in_(open_statuses), SupportTicket.due_date != None, SupportTicket.due_date < today).count(),
        'warranties': WarrantyRegistration.query.count(),
    }
    return render_template('support/dashboard.html', tickets=tickets, warranties=warranties, summary=summary)

@support_bp.route('/warranties')
@login_required
def warranties():
    warranties = WarrantyRegistration.query.order_by(WarrantyRegistration.created_at.desc()).all()
    return render_template('support/warranties.html', warranties=warranties)

@support_bp.route('/warranties/create', methods=['GET','POST'])
@login_required
def create_warranty():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id') or None
        customer = Customer.query.get(customer_id) if customer_id else None
        warranty = WarrantyRegistration(
            ref_no=make_ref('WRN'), project_id=request.form.get('project_id') or None,
            customer_id=customer_id, customer_name=request.form.get('customer_name') or (customer.customer_name if customer else ''),
            system_type=request.form.get('system_type'), capacity=request.form.get('capacity'),
            installation_date=parse_date(request.form.get('installation_date')),
            handover_date=parse_date(request.form.get('handover_date')),
            warranty_start=parse_date(request.form.get('warranty_start')), warranty_end=parse_date(request.form.get('warranty_end')),
            status=request.form.get('status') or 'Active', registered_by_id=current_user.id, notes=request.form.get('notes'))
        db.session.add(warranty); db.session.commit(); flash(f'Warranty {warranty.ref_no} created.', 'success')
        return redirect(url_for('support.warranty_detail', warranty_id=warranty.id))
    return render_template('support/warranty_form.html', projects=Project.query.order_by(Project.project_name.asc()).all(), customers=Customer.query.order_by(Customer.customer_name.asc()).all(), statuses=WARRANTY_STATUSES)

@support_bp.route('/warranties/<int:warranty_id>')
@login_required
def warranty_detail(warranty_id):
    warranty = WarrantyRegistration.query.get_or_404(warranty_id)
    return render_template('support/warranty_detail.html', warranty=warranty)

@support_bp.route('/tickets')
@login_required
def tickets():
    query = SupportTicket.query
    status = request.args.get('status')
    priority = request.args.get('priority')
    category = request.args.get('category')
    search = request.args.get('search')
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(issue_category=category)
    if search:
        like = f"%{search}%"
        query = query.filter((SupportTicket.customer_name.ilike(like)) | (SupportTicket.ref_no.ilike(like)) | (SupportTicket.issue_description.ilike(like)))
    tickets = query.order_by(SupportTicket.created_at.desc()).all()
    return render_template('support/tickets.html', tickets=tickets, statuses=TICKET_STATUSES, priorities=TICKET_PRIORITIES, categories=TICKET_CATEGORIES, filters=request.args)

@support_bp.route('/tickets/create', methods=['GET','POST'])
@login_required
def create_ticket():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id') or None
        customer = Customer.query.get(customer_id) if customer_id else None
        due_date = parse_date(request.form.get('due_date'))
        if not due_date:
            priority = request.form.get('priority') or 'Medium'
            days = 1 if priority == 'Urgent' else 2 if priority == 'High' else 5
            due_date = date.today() + timedelta(days=days)
        ticket = SupportTicket(
            ref_no=make_ref('TKT'), ticket_date=parse_date(request.form.get('ticket_date')) or date.today(),
            customer_id=customer_id, project_id=request.form.get('project_id') or None, warranty_id=request.form.get('warranty_id') or None,
            customer_name=request.form.get('customer_name') or (customer.customer_name if customer else ''),
            phone=request.form.get('phone'), location=request.form.get('location'), complaint_source=request.form.get('complaint_source'),
            preferred_visit_date=parse_date(request.form.get('preferred_visit_date')), due_date=due_date,
            issue_category=request.form.get('issue_category'), issue_description=request.form.get('issue_description'),
            priority=request.form.get('priority') or 'Medium', status=request.form.get('status') or 'Open',
            assigned_employee_id=request.form.get('assigned_employee_id') or None, supervisor_user_id=request.form.get('supervisor_user_id') or None,
            created_by_id=current_user.id)
        db.session.add(ticket); db.session.flush()
        # Phase 15E: automatically notify supervisor and technician user account if linked to employee.
        msg = f"Service Ticket {ticket.ref_no} created for {ticket.customer_name}. Priority: {ticket.priority}. Issue: {ticket.issue_category or 'General'}"
        if ticket.supervisor:
            create_notification_event("New Service Ticket Assigned", msg, target_user=ticket.supervisor, priority=ticket.priority, category="Service Ticket", related_module="Support Ticket", related_ref=ticket.ref_no, send_email_now=False, queue_sms=True, created_by_id=current_user.id)
        if ticket.assigned_employee and ticket.assigned_employee.user_account:
            create_notification_event("Service Ticket Assigned to You", msg, target_user=ticket.assigned_employee.user_account, priority=ticket.priority, category="Service Ticket", related_module="Support Ticket", related_ref=ticket.ref_no, send_email_now=False, queue_sms=True, created_by_id=current_user.id)
        db.session.commit(); flash(f'Ticket {ticket.ref_no} created and notifications queued.', 'success')
        return redirect(url_for('support.ticket_detail', ticket_id=ticket.id))
    return render_template('support/ticket_form.html',
        projects=Project.query.order_by(Project.project_name.asc()).all(),
        customers=Customer.query.order_by(Customer.customer_name.asc()).all(),
        employees=Employee.query.filter_by(status='Active').all(), users=User.query.filter_by(is_active=True).all(),
        warranties=WarrantyRegistration.query.order_by(WarrantyRegistration.created_at.desc()).all(),
        statuses=TICKET_STATUSES, priorities=TICKET_PRIORITIES, categories=TICKET_CATEGORIES, sources=COMPLAINT_SOURCES)

@support_bp.route('/tickets/<int:ticket_id>')
@login_required
def ticket_detail(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    employees = Employee.query.filter_by(status='Active').all()
    users = User.query.filter_by(is_active=True).all()
    return render_template('support/ticket_detail.html', ticket=ticket, employees=employees, users=users, statuses=TICKET_STATUSES,
                           visit_statuses=VISIT_STATUSES, service_results=SERVICE_RESULTS, confirmations=CUSTOMER_CONFIRMATIONS)

@support_bp.route('/tickets/<int:ticket_id>/update', methods=['POST'])
@login_required
def update_ticket(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    for field in ['priority', 'status', 'issue_category', 'location', 'complaint_source', 'root_cause', 'corrective_action', 'preventive_action', 'final_result', 'customer_confirmation', 'resolution_summary']:
        if field in request.form:
            setattr(ticket, field, request.form.get(field))
    ticket.due_date = parse_date(request.form.get('due_date')) or ticket.due_date
    ticket.preferred_visit_date = parse_date(request.form.get('preferred_visit_date')) or ticket.preferred_visit_date
    ticket.assigned_employee_id = request.form.get('assigned_employee_id') or None
    ticket.supervisor_user_id = request.form.get('supervisor_user_id') or None
    if ticket.status in ['Closed', 'Resolved', 'Not Warranty'] and not ticket.closed_at:
        ticket.closed_at = datetime.utcnow()
    if ticket.supervisor:
        create_notification_event("Service Ticket Updated", f"Ticket {ticket.ref_no} status updated to {ticket.status}.", target_user=ticket.supervisor, priority=ticket.priority, category="Service Ticket", related_module="Support Ticket", related_ref=ticket.ref_no, send_email_now=False, queue_sms=False, created_by_id=current_user.id)
    db.session.commit(); flash('Ticket updated and notification logged.', 'success')
    return redirect(url_for('support.ticket_detail', ticket_id=ticket.id))

@support_bp.route('/tickets/<int:ticket_id>/visit', methods=['POST'])
@login_required
def add_visit(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    visit = ServiceVisit(
        ref_no=make_ref('SVR'), ticket_id=ticket.id, visit_date=parse_date(request.form.get('visit_date')) or date.today(),
        technician_employee_id=request.form.get('technician_employee_id') or ticket.assigned_employee_id,
        fault_found=request.form.get('fault_found'), root_cause=request.form.get('root_cause'), work_done=request.form.get('work_done'),
        parts_used=request.form.get('parts_used'), result=request.form.get('result'), test_result=request.form.get('test_result'),
        customer_feedback=request.form.get('customer_feedback'), customer_confirmation=request.form.get('customer_confirmation'),
        next_action=request.form.get('next_action'), status=request.form.get('status') or 'Completed')
    db.session.add(visit)
    if request.form.get('close_ticket') == 'on':
        ticket.status = 'Closed'; ticket.resolution_summary = request.form.get('work_done'); ticket.final_result = request.form.get('result'); ticket.customer_confirmation = request.form.get('customer_confirmation'); ticket.closed_at = datetime.utcnow()
    elif request.form.get('result') == 'Needs Parts':
        ticket.status = 'Waiting Parts'
    elif request.form.get('result') in ['Resolved', 'Partially Resolved']:
        ticket.status = 'Resolved'
    else:
        ticket.status = 'In Progress'
    if request.form.get('root_cause'):
        ticket.root_cause = request.form.get('root_cause')
    db.session.commit(); flash('Service visit saved.', 'success')
    return redirect(url_for('support.ticket_detail', ticket_id=ticket.id))

@support_bp.route('/tickets/<int:ticket_id>/report')
@login_required
def ticket_report(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    return render_template('support/ticket_report.html', ticket=ticket, generated_at=datetime.utcnow())

@support_bp.route('/tickets/<int:ticket_id>/pdf')
@login_required
def ticket_pdf(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    html = render_template('support/ticket_report.html', ticket=ticket, generated_at=datetime.utcnow(), pdf_mode=True)
    try:
        from weasyprint import HTML
        pdf = HTML(string=html, base_url=request.host_url).write_pdf()
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename={ticket.ref_no}.pdf'
        return response
    except Exception:
        flash('PDF engine is not available. Print view opened instead.', 'warning')
        return html
