from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.ai_service import call_ai, make_ai_ref, CADCEED_SYSTEM_PROMPT
from app.models import (
    AISetting, AIInteractionLog, AI_CONTEXT_TYPES, AI_RESPONSE_STATUSES,
    Project, ProjectTask, SupportTicket, SalesInquiry, SalesQuotation,
    SystemNotification
)

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

@ai_bp.before_app_request
def ensure_ai_tables():
    try:
        db.create_all()
    except Exception:
        pass

def get_setting():
    setting = AISetting.query.first()
    if not setting:
        setting = AISetting(enabled=True, system_prompt=CADCEED_SYSTEM_PROMPT, notes='Local offline AI mode is enabled. Add API key for live AI.')
        db.session.add(setting)
        db.session.commit()
    return setting

def save_log(context_type, prompt, response, context_data='', related_module=None, related_ref=None, error=None):
    setting = get_setting()
    log = AIInteractionLog(
        ref_no=make_ai_ref(), user_id=current_user.id,
        context_type=context_type or 'General ERP Question', related_module=related_module,
        related_ref=related_ref, prompt=prompt, context_data=context_data,
        response=response, provider=setting.provider, model_name=setting.model_name,
        error_message=error
    )
    db.session.add(log); db.session.commit()
    return log

@ai_bp.route('/')
@login_required
def dashboard():
    setting = get_setting()
    stats = {
        'logs': AIInteractionLog.query.count(),
        'today': AIInteractionLog.query.filter(AIInteractionLog.created_at >= datetime.utcnow().date()).count(),
        'errors': AIInteractionLog.query.filter(AIInteractionLog.error_message != None).count(),
        'tickets': SupportTicket.query.count(),
        'crm': SalesInquiry.query.count(),
    }
    latest = AIInteractionLog.query.order_by(AIInteractionLog.created_at.desc()).limit(8).all()
    return render_template('ai/dashboard.html', setting=setting, stats=stats, latest=latest)

@ai_bp.route('/assistant', methods=['GET','POST'])
@login_required
def assistant():
    setting = get_setting()
    result = None
    log = None
    selected_context_type = 'General ERP Question'
    last_prompt = ''
    last_context_data = ''

    if request.method == 'POST':
        selected_context_type = request.form.get('context_type') or 'General ERP Question'
        last_prompt = (request.form.get('prompt') or '').strip()
        last_context_data = request.form.get('context_data') or ''

        if not last_prompt:
            flash('Please write a question/request before generating AI response.', 'danger')
        else:
            response, error = call_ai(setting, last_prompt, context_data=last_context_data)
            log = save_log(selected_context_type, last_prompt, response, context_data=last_context_data, error=error)
            result = response
            if error:
                flash('AI returned a local/offline response. Add API key in AI Settings for live AI.', 'warning')
            else:
                flash('AI response generated and saved in AI log.', 'success')

    # Phase 15I: On normal page open, do NOT show the previous AI answer.
    # The page should start clean and only display a response after the user submits a new question.

    return render_template(
        'ai/assistant.html',
        context_types=AI_CONTEXT_TYPES,
        result=result,
        log=log,
        setting=setting,
        selected_context_type=selected_context_type,
        last_prompt=last_prompt,
        last_context_data=last_context_data,
    )

@ai_bp.route('/service-ticket/<int:ticket_id>', methods=['GET','POST'])
@login_required
def service_ticket_helper(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    setting = get_setting()
    context_data = f"""
Ticket: {ticket.ref_no}
Customer: {ticket.customer_name}
Phone: {ticket.phone or ''}
Location: {ticket.location or ''}
Category: {ticket.issue_category or ''}
Priority: {ticket.priority}
Status: {ticket.status}
Issue: {ticket.issue_description}
Assigned Technician: {ticket.assigned_employee.full_name if ticket.assigned_employee else ''}
Supervisor: {ticket.supervisor.full_name if ticket.supervisor else ''}
Root Cause: {ticket.root_cause or ''}
Corrective Action: {ticket.corrective_action or ''}
Resolution: {ticket.resolution_summary or ''}
""".strip()
    default_prompt = "Analyze this service ticket. Suggest category, priority, likely root cause, technician checklist, customer reply, and next action."
    result = None; log = None
    if request.method == 'POST':
        prompt = request.form.get('prompt') or default_prompt
        response, error = call_ai(setting, prompt, context_data=context_data)
        log = save_log('Service Ticket Help', prompt, response, context_data=context_data, related_module='Support Ticket', related_ref=ticket.ref_no, error=error)
        result = response
        flash('AI service ticket suggestion saved.', 'success' if not error else 'warning')
    return render_template('ai/service_ticket_helper.html', ticket=ticket, context_data=context_data, default_prompt=default_prompt, result=result, log=log)

@ai_bp.route('/crm-inquiry/<int:inquiry_id>', methods=['GET','POST'])
@login_required
def crm_helper(inquiry_id):
    inquiry = SalesInquiry.query.get_or_404(inquiry_id)
    setting = get_setting()
    context_data = f"""
Inquiry: {inquiry.ref_no}
Customer: {inquiry.customer_name}
Phone: {inquiry.phone or ''}
Location: {inquiry.location or ''}
Source: {inquiry.source}
Project Type: {inquiry.project_type or ''}
Estimated Capacity: {inquiry.estimated_capacity or ''}
Status: {inquiry.status}
Requirement: {inquiry.requirement_summary or ''}
Next Follow-up: {inquiry.next_followup_date or ''}
Notes: {inquiry.notes or ''}
""".strip()
    default_prompt = "Create a professional CRM follow-up plan and a short WhatsApp message for this customer. Also classify the lead as Hot, Warm, or Cold."
    result = None; log = None
    if request.method == 'POST':
        prompt = request.form.get('prompt') or default_prompt
        response, error = call_ai(setting, prompt, context_data=context_data)
        log = save_log('CRM Follow-up', prompt, response, context_data=context_data, related_module='Sales Inquiry', related_ref=inquiry.ref_no, error=error)
        result = response
        flash('AI CRM suggestion saved.', 'success' if not error else 'warning')
    return render_template('ai/crm_helper.html', inquiry=inquiry, context_data=context_data, default_prompt=default_prompt, result=result, log=log)

@ai_bp.route('/reports', methods=['GET','POST'])
@login_required
def reports():
    setting = get_setting(); result = None; log = None
    report_type = request.form.get('report_type') if request.method == 'POST' else ''
    context_data = ''
    if request.method == 'POST':
        open_tickets = SupportTicket.query.filter(SupportTicket.status.in_(['Open','Assigned','In Progress','Waiting Parts','Pending Customer'])).limit(20).all()
        recent_projects = Project.query.order_by(Project.created_at.desc()).limit(15).all()
        recent_inquiries = SalesInquiry.query.order_by(SalesInquiry.created_at.desc()).limit(15).all()
        context_data = "PROJECTS:\n" + "\n".join([f"- {p.project_name} | {p.customer_name} | {p.status} | {p.capacity or ''}" for p in recent_projects])
        context_data += "\n\nOPEN SERVICE TICKETS:\n" + "\n".join([f"- {t.ref_no} | {t.customer_name} | {t.priority} | {t.status} | {t.issue_category}" for t in open_tickets])
        context_data += "\n\nRECENT CRM INQUIRIES:\n" + "\n".join([f"- {i.ref_no} | {i.customer_name} | {i.status} | {i.project_type or ''}" for i in recent_inquiries])
        prompt = request.form.get('prompt') or f"Generate a professional {report_type or 'operations'} report for management with risks, priorities, and next actions."
        response, error = call_ai(setting, prompt, context_data=context_data)
        log = save_log('Weekly Report', prompt, response, context_data=context_data, related_module='AI Reports', related_ref=report_type, error=error)
        result = response
        flash('AI report draft saved.', 'success' if not error else 'warning')
    return render_template('ai/reports.html', result=result, log=log)

@ai_bp.route('/logs')
@login_required
def logs():
    context_type = request.args.get('context_type')
    query = AIInteractionLog.query
    if context_type:
        query = query.filter_by(context_type=context_type)
    logs = query.order_by(AIInteractionLog.created_at.desc()).limit(500).all()
    return render_template('ai/logs.html', logs=logs, context_types=AI_CONTEXT_TYPES)

@ai_bp.route('/logs/<int:log_id>/status', methods=['POST'])
@login_required
def update_log_status(log_id):
    log = AIInteractionLog.query.get_or_404(log_id)
    log.status = request.form.get('status') or log.status
    if log.status in ['Reviewed', 'Used']:
        log.reviewed_at = datetime.utcnow()
    db.session.commit(); flash('AI log status updated.', 'success')
    return redirect(url_for('ai.logs'))

@ai_bp.route('/settings', methods=['GET','POST'])
@login_required
def settings():
    if current_user.role != 'Admin':
        flash('Only admin can change AI settings.', 'danger')
        return redirect(url_for('ai.dashboard'))
    setting = get_setting()
    if request.method == 'POST':
        setting.enabled = request.form.get('enabled') == 'on'
        setting.provider = request.form.get('provider') or 'OpenAI-Compatible'
        setting.model_name = request.form.get('model_name') or setting.model_name
        setting.api_base_url = request.form.get('api_base_url') or setting.api_base_url
        if request.form.get('api_key'):
            setting.api_key = request.form.get('api_key')
        setting.temperature = float(request.form.get('temperature') or 0.2)
        setting.max_tokens = int(request.form.get('max_tokens') or 900)
        setting.system_prompt = request.form.get('system_prompt') or CADCEED_SYSTEM_PROMPT
        setting.allow_data_context = request.form.get('allow_data_context') == 'on'
        setting.notes = request.form.get('notes')
        setting.updated_by_id = current_user.id
        db.session.commit(); flash('AI settings saved.', 'success')
        return redirect(url_for('ai.settings'))
    masked_key = 'Saved / Environment Key Available' if setting.api_key else 'Use OPENAI_API_KEY environment variable or enter key'
    return render_template('ai/settings.html', setting=setting, masked_key=masked_key)