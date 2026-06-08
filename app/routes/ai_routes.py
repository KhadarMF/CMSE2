from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from sqlalchemy import text
from app.ai_service import call_ai, make_ai_ref, CADCEED_SYSTEM_PROMPT, test_ai_connection, get_api_key
from app.permissions import can_access_module
from app.models import (
    AISetting, AIInteractionLog, AI_CONTEXT_TYPES, AI_RESPONSE_STATUSES,
    Project, ProjectTask, ProjectIssue, SupportTicket, SalesInquiry, SalesQuotation, SalesQuotationLine,
    MaterialItem, SiteSurveyForm, LoadAssessmentForm, DailySiteReport, DeliveryNoteForm,
    TestingForm, CommissioningForm, HandoverForm, SystemNotification
)

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')


PHASE1_FORM_MAP = {
    'site-survey': ('Site Survey & Load Assessment', SiteSurveyForm),
    'load-assessment': ('Load Assessment', LoadAssessmentForm),
    'daily-site-report': ('Daily Site Report', DailySiteReport),
    'delivery-note': ('Delivery Note', DeliveryNoteForm),
    'testing': ('Testing Report', TestingForm),
    'commissioning': ('Commissioning Form', CommissioningForm),
    'handover': ('Handover Certificate', HandoverForm),
}

REPORT_FIELD_MAP = {
    'site-survey': ['site_name','survey_date','surveyed_by','gps_coordinates','roof_type','roof_condition','available_space','shading_status','existing_power_source','earthing_condition','access_road','assessment_date','assessed_by','daytime_load_kw','nighttime_load_kw','total_daily_consumption_kwh','critical_loads','ac_loads','pump_loads','lighting_loads','backup_hours_required','recommended_system_size','recommendation','remarks'],
    'load-assessment': ['assessment_date','assessed_by','daytime_load_kw','nighttime_load_kw','total_daily_consumption_kwh','critical_loads','ac_loads','pump_loads','lighting_loads','backup_hours_required','recommended_system_size','remarks'],
    'daily-site-report': ['report_date','site_supervisor','manpower','work_done_today','materials_used','tools_equipment_used','issues_challenges','safety_notes','next_day_plan','progress_percentage','remarks'],
    'delivery-note': ['delivery_date','delivered_by','received_by','vehicle_plate','delivery_location','items_delivered','quantity_summary','condition_of_items','receiver_comments','remarks'],
    'testing': ['testing_date','tested_by','inverter_status','pv_voltage','battery_voltage','output_voltage','load_test_result','protection_test_result','faults_found','corrective_actions','test_result','remarks'],
    'commissioning': ['commissioning_date','commissioned_by','system_capacity','inverter_model','battery_model','pv_array_details','battery_settings','inverter_settings','monitoring_setup','client_training_done','commissioning_status','remarks'],
    'handover': ['handover_date','handed_over_by','received_by','documents_handed_over','spare_parts_handed_over','training_provided','warranty_explained','client_comments','final_status','remarks'],
}


def _require_ai_permission(key):
    if not can_access_module(current_user, key, 'view'):
        flash('Access Denied: You do not have permission to use this AI module.', 'danger')
        return False
    return True


def _format_value(value):
    if value is None or value == '':
        return 'Not provided'
    try:
        return value.strftime('%Y-%m-%d')
    except Exception:
        return str(value)


def _project_context(project):
    return f"""
Project Name: {project.project_name}
Customer: {project.customer_name}
Location: {project.location}
Project Type: {project.project_type}
Capacity: {project.capacity or 'Not provided'}
Status: {project.status}
Start Date: {_format_value(project.start_date)}
Expected Completion: {_format_value(project.expected_completion_date)}
Assigned Team: {project.assigned_team or 'Not provided'}
Description: {project.description or 'Not provided'}
""".strip()


def _form_context(form_key, entry):
    lines = [_project_context(entry.project), f"Form Type: {PHASE1_FORM_MAP[form_key][0]}", f"Form ID: {entry.id}", f"Approval Status: {entry.approval_status}", f"Created By: {entry.creator.full_name if entry.creator else 'Not provided'}"]
    for field in REPORT_FIELD_MAP.get(form_key, []):
        label = field.replace('_', ' ').title()
        lines.append(f"{label}: {_format_value(getattr(entry, field, None))}")
    return '\n'.join(lines)


def _quotation_context(quotation=None):
    if not quotation:
        return ''
    lines = [
        f"Quotation Ref: {quotation.ref_no}",
        f"Customer: {quotation.customer_name}",
        f"Project Type: {quotation.project_type or 'Not provided'}",
        f"Capacity: {quotation.capacity or 'Not provided'}",
        f"Status: {quotation.status}",
        f"Scope of Work: {quotation.scope_of_work or 'Not provided'}",
        f"Validity Days: {quotation.validity_days}",
        f"Prepared By: {quotation.prepared_by.full_name if quotation.prepared_by else 'Not provided'}",
        f"Notes: {quotation.notes or 'Not provided'}",
        "Items:"
    ]
    for line in quotation.lines:
        lines.append(f"- {line.item} | {line.description or ''} | Qty: {line.quantity} {line.unit or ''} | Unit Price: {line.unit_price}")
    return '\n'.join(lines)


def _stock_context(limit=120, include_cost=False):
    items = MaterialItem.query.filter_by(is_active=True).order_by(MaterialItem.category.asc(), MaterialItem.item_name.asc()).limit(limit).all()
    rows = []
    for item in items:
        cost = f" | Unit Cost: {item.unit_cost}" if include_cost else ""
        rows.append(f"- {item.item_code or ''} | {item.item_name} | Category: {item.category or ''} | Unit: {item.unit or ''} | Description: {item.description or ''}{cost}")
    return '\n'.join(rows) if rows else 'No active material items found.'


def _default_report_prompt(form_title):
    return f"PHASE1_PROJECT_REPORT: Generate a formal {form_title} for Cadceed-Maal Solar Energy. Include Project Information, Work Completed/Details, Materials or Measurements, Pending Work, Issues/Risks, Required Actions, Next Plan, and Professional Summary. Mark it as DRAFT until approved."


def _default_quotation_prompt():
    return "PHASE1_QUOTATION: Generate a draft solar quotation and customer proposal. Include customer need summary, recommended system, PV sizing draft, inverter sizing draft, battery sizing draft, BOQ draft, assumptions, warranty note, payment terms placeholder, proposal text, WhatsApp follow-up, and approval reminder."


def _default_stock_prompt(question):
    return f"PHASE1_STOCK: Answer this stock/material question using only the provided ERP material data. Question: {question}"

@ai_bp.before_app_request
def ensure_ai_tables():
    try:
        db.create_all()
        inspector = db.inspect(db.engine)
        # Phase 16B lightweight database upgrade for PostgreSQL/SQLite existing deployments.
        if inspector.has_table("sales_inquiry"):
            inquiry_cols = [c["name"] for c in inspector.get_columns("sales_inquiry")]
            inquiry_ai_columns = {
                "ai_opportunity_score": "VARCHAR(80)",
                "ai_lead_temperature": "VARCHAR(80)",
                "ai_followup_text": "TEXT",
                "ai_recommended_action": "TEXT",
                "ai_last_followup": "TIMESTAMP",
            }
            for col, col_type in inquiry_ai_columns.items():
                if col not in inquiry_cols:
                    db.session.execute(text(f"ALTER TABLE sales_inquiry ADD COLUMN {col} {col_type}"))
        if inspector.has_table("project"):
            project_cols = [c["name"] for c in inspector.get_columns("project")]
            project_ai_columns = {
                "ai_health_score": "VARCHAR(80)",
                "ai_risk_level": "VARCHAR(80)",
                "ai_delay_prediction": "VARCHAR(120)",
                "ai_project_summary": "TEXT",
                "ai_recommended_actions": "TEXT",
                "ai_last_analysis": "TIMESTAMP",
            }
            for col, col_type in project_ai_columns.items():
                if col not in project_cols:
                    db.session.execute(text(f"ALTER TABLE project ADD COLUMN {col} {col_type}"))
        db.session.commit()
    except Exception:
        db.session.rollback()

def get_setting():
    setting = AISetting.query.first()
    if not setting:
        setting = AISetting(
            enabled=True,
            provider='OpenAI Responses API',
            model_name='gpt-4o-mini',
            api_base_url='https://api.openai.com/v1/responses',
            system_prompt=CADCEED_SYSTEM_PROMPT,
            notes='Live AI mode. Put OPENAI_API_KEY in server environment variables or enter API key here.'
        )
        db.session.add(setting)
        db.session.commit()
    else:
        # Upgrade old default endpoint to the current Responses API unless user intentionally set a custom URL.
        if not setting.api_base_url or setting.api_base_url.strip() == 'https://api.openai.com/v1/chat/completions':
            setting.provider = setting.provider or 'OpenAI Responses API'
            setting.api_base_url = 'https://api.openai.com/v1/responses'
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



@ai_bp.route('/project-report', methods=['GET', 'POST'])
@login_required
def project_report_ai():
    if not _require_ai_permission('ai-project-report'):
        return redirect(url_for('ai.dashboard'))
    setting = get_setting(); result = None; log = None; selected_form_key = request.values.get('form_key') or 'daily-site-report'; selected_form_id = request.values.get('form_id') or ''
    entries = []
    if selected_form_key in PHASE1_FORM_MAP:
        title, Model = PHASE1_FORM_MAP[selected_form_key]
        entries = Model.query.order_by(Model.created_at.desc()).limit(100).all()
    if request.method == 'POST':
        if selected_form_key not in PHASE1_FORM_MAP:
            flash('Invalid form type.', 'danger')
            return redirect(url_for('ai.project_report_ai'))
        title, Model = PHASE1_FORM_MAP[selected_form_key]
        entry = Model.query.get_or_404(request.form.get('form_id'))
        context_data = _form_context(selected_form_key, entry)
        prompt = request.form.get('prompt') or _default_report_prompt(title)
        response, error = call_ai(setting, prompt, context_data=context_data)
        log = save_log('AI Project Report Writer', prompt, response, context_data=context_data, related_module=title, related_ref=f'{selected_form_key}-{entry.id}', error=error)
        result = response
        flash('AI project report draft generated and saved in AI logs.', 'success' if not error else 'warning')
    return render_template('ai/phase1_project_report.html', result=result, log=log, form_map=PHASE1_FORM_MAP, selected_form_key=selected_form_key, selected_form_id=str(selected_form_id), entries=entries, default_prompt=_default_report_prompt(PHASE1_FORM_MAP.get(selected_form_key, ('Project Report', None))[0]))


@ai_bp.route('/project-report/<form_key>/<int:form_id>', methods=['GET', 'POST'])
@login_required
def project_report_from_form(form_key, form_id):
    if not _require_ai_permission('ai-project-report'):
        return redirect(url_for('ai.dashboard'))
    if form_key not in PHASE1_FORM_MAP:
        flash('Invalid form type.', 'danger')
        return redirect(url_for('ai.project_report_ai'))
    title, Model = PHASE1_FORM_MAP[form_key]
    entry = Model.query.get_or_404(form_id)
    setting = get_setting(); result = None; log = None
    context_data = _form_context(form_key, entry)
    default_prompt = _default_report_prompt(title)
    if request.method == 'POST':
        prompt = request.form.get('prompt') or default_prompt
        response, error = call_ai(setting, prompt, context_data=context_data)
        log = save_log('AI Project Report Writer', prompt, response, context_data=context_data, related_module=title, related_ref=f'{form_key}-{entry.id}', error=error)
        result = response
        flash('AI project report draft generated and saved in AI logs.', 'success' if not error else 'warning')
    return render_template('ai/phase1_project_report_single.html', result=result, log=log, form_key=form_key, form_title=title, entry=entry, context_data=context_data, default_prompt=default_prompt)


@ai_bp.route('/quotation-draft', methods=['GET', 'POST'])
@login_required
def quotation_ai():
    if not _require_ai_permission('ai-quotation'):
        return redirect(url_for('ai.dashboard'))
    setting = get_setting(); result = None; log = None
    quotations = SalesQuotation.query.order_by(SalesQuotation.created_at.desc()).limit(100).all()
    selected_quotation_id = request.values.get('quotation_id') or ''
    quotation = SalesQuotation.query.get(selected_quotation_id) if selected_quotation_id else None
    context_data = _quotation_context(quotation) if quotation else ''
    manual_context = ''
    if request.method == 'POST':
        quotation = SalesQuotation.query.get(request.form.get('quotation_id')) if request.form.get('quotation_id') else None
        context_data = _quotation_context(quotation) if quotation else ''
        manual_context = request.form.get('manual_context') or ''
        if manual_context:
            context_data = (context_data + '\n\nManual Customer / Load Data:\n' + manual_context).strip()
        prompt = request.form.get('prompt') or _default_quotation_prompt()
        if not context_data:
            flash('Please select a quotation or enter customer/load details.', 'danger')
        else:
            response, error = call_ai(setting, prompt, context_data=context_data)
            related_ref = quotation.ref_no if quotation else 'Manual quotation draft'
            log = save_log('AI Quotation Draft Generator', prompt, response, context_data=context_data, related_module='Sales Quotation', related_ref=related_ref, error=error)
            result = response
            flash('AI quotation draft generated and saved in AI logs.', 'success' if not error else 'warning')
    return render_template('ai/phase1_quotation.html', result=result, log=log, quotations=quotations, selected_quotation_id=str(selected_quotation_id), default_prompt=_default_quotation_prompt(), manual_context=manual_context)


@ai_bp.route('/quotation-draft/<int:quotation_id>', methods=['GET', 'POST'])
@login_required
def quotation_from_record(quotation_id):
    if not _require_ai_permission('ai-quotation'):
        return redirect(url_for('ai.dashboard'))
    quotation = SalesQuotation.query.get_or_404(quotation_id)
    setting = get_setting(); result = None; log = None
    context_data = _quotation_context(quotation)
    default_prompt = _default_quotation_prompt()
    if request.method == 'POST':
        prompt = request.form.get('prompt') or default_prompt
        response, error = call_ai(setting, prompt, context_data=context_data)
        log = save_log('AI Quotation Draft Generator', prompt, response, context_data=context_data, related_module='Sales Quotation', related_ref=quotation.ref_no, error=error)
        result = response
        flash('AI quotation draft generated and saved in AI logs.', 'success' if not error else 'warning')
    return render_template('ai/phase1_quotation_single.html', result=result, log=log, quotation=quotation, context_data=context_data, default_prompt=default_prompt)


@ai_bp.route('/stock-assistant', methods=['GET', 'POST'])
@login_required
def stock_ai():
    if not _require_ai_permission('ai-stock'):
        return redirect(url_for('ai.dashboard'))
    setting = get_setting(); result = None; log = None
    question = request.form.get('question') if request.method == 'POST' else (request.args.get('q') or '')
    include_cost = current_user.role in ['Admin', 'Management', 'Finance Officer']
    stock_data = _stock_context(include_cost=include_cost)
    if request.method == 'POST':
        if not question:
            flash('Please write a stock question.', 'danger')
        else:
            prompt = _default_stock_prompt(question)
            context_data = f"User Role: {current_user.role}\nPermission: {'Cost allowed' if include_cost else 'Hide cost and selling price'}\n\nStock Data:\n{stock_data}"
            response, error = call_ai(setting, prompt, context_data=context_data)
            log = save_log('AI Stock Assistant', prompt, response, context_data=context_data, related_module='Materials', related_ref=question[:100], error=error)
            result = response
            flash('AI stock answer generated and saved in AI logs.', 'success' if not error else 'warning')
    return render_template('ai/phase1_stock.html', result=result, log=log, question=question, stock_data=stock_data, include_cost=include_cost)




def _crm_inquiry_context(inquiry):
    quotes = SalesQuotation.query.filter_by(inquiry_id=inquiry.id).order_by(SalesQuotation.created_at.desc()).limit(5).all()
    quote_lines = []
    for q in quotes:
        quote_lines.append(f"- {q.ref_no} | Status: {q.status} | Total: {q.total_amount:.2f} | Date: {_format_value(q.quotation_date)} | Scope: {q.scope_of_work or ''}")
    return f"""
CRM Inquiry Ref: {inquiry.ref_no}
Customer: {inquiry.customer_name}
Phone: {inquiry.phone or 'Not provided'}
Location: {inquiry.location or 'Not provided'}
Source: {inquiry.source or 'Not provided'}
Project Type: {inquiry.project_type or 'Not provided'}
Estimated Capacity: {inquiry.estimated_capacity or 'Not provided'}
Status: {inquiry.status}
Requirement Summary: {inquiry.requirement_summary or 'Not provided'}
Next Follow-up Date: {_format_value(inquiry.next_followup_date)}
Notes: {inquiry.notes or 'Not provided'}
Created At: {_format_value(inquiry.created_at)}
Previous AI Opportunity Score: {inquiry.ai_opportunity_score or 'Not provided'}
Previous AI Lead Temperature: {inquiry.ai_lead_temperature or 'Not provided'}
Related Quotations:
{chr(10).join(quote_lines) if quote_lines else 'No quotations found for this inquiry.'}
""".strip()


def _crm_agent_prompt():
    return """PHASE16B_AI_CRM_AGENT: Analyze this CRM inquiry for Cadceed-Maal Solar Energy.
Return a practical CRM output with these sections:
1. Lead Temperature: Hot / Warm / Cold
2. Opportunity Score: 0-100%
3. Customer Need Summary
4. Recommended Next Action
5. WhatsApp Follow-up Message in Somali
6. WhatsApp Follow-up Message in English
7. Email Follow-up Draft
8. Sales Objection Handling Notes
9. Manager Notes
Rules: Be professional, concise, customer-friendly, and do not invent prices or stock."""


def _project_manager_context(project):
    tasks = ProjectTask.query.filter_by(project_id=project.id).order_by(ProjectTask.created_at.desc()).limit(20).all()
    issues = ProjectIssue.query.filter_by(project_id=project.id).order_by(ProjectIssue.reported_at.desc()).limit(20).all()
    forms_summary = f"Site Surveys: {len(project.site_surveys)} | Load Assessments: {len(project.load_assessments)} | Daily Reports: {len(project.daily_reports)} | Delivery Notes: {len(project.delivery_notes)} | Testing: {len(project.testing_forms)} | Commissioning: {len(project.commissioning_forms)} | Handover: {len(project.handover_forms)}"
    task_lines = []
    for t in tasks:
        task_lines.append(f"- {t.title} | Status: {t.status} | Priority: {t.priority} | Due: {_format_value(t.due_date)} | Assigned: {t.assigned_to.full_name if t.assigned_to else 'Not assigned'}")
    issue_lines = []
    for i in issues:
        issue_lines.append(f"- {i.title} | Severity: {i.severity} | Status: {i.status} | Responsible: {i.responsible_user.full_name if i.responsible_user else 'Not assigned'}")
    return f"""
Project Name: {project.project_name}
Customer: {project.customer_name}
Location: {project.location}
Project Type: {project.project_type}
Capacity: {project.capacity or 'Not provided'}
Status: {project.status}
Start Date: {_format_value(project.start_date)}
Expected Completion: {_format_value(project.expected_completion_date)}
Assigned Team: {project.assigned_team or 'Not provided'}
Description: {project.description or 'Not provided'}
Forms Summary: {forms_summary}
Tasks:
{chr(10).join(task_lines) if task_lines else 'No tasks found.'}
Issues/Risks:
{chr(10).join(issue_lines) if issue_lines else 'No issues/risks found.'}
Previous AI Health Score: {project.ai_health_score or 'Not provided'}
Previous AI Risk Level: {project.ai_risk_level or 'Not provided'}
""".strip()


def _project_manager_prompt():
    return """PHASE16B_AI_PROJECT_MANAGER: Analyze this project for Cadceed-Maal Solar Energy.
Return a practical project management output with these sections:
1. Project Health Score: 0-100%
2. Risk Level: Low / Medium / High / Critical
3. Delay Prediction
4. Progress Summary
5. Key Risks
6. Recommended Actions
7. Required Management Decisions
8. Team / Resource Notes
9. Customer Communication Note
Rules: Use only the ERP data provided. If dates/tasks are missing, clearly say what data is missing."""


def _extract_value_from_response(response, label):
    """Best-effort extraction for common lines like 'Opportunity Score: 80%'."""
    if not response:
        return None
    import re
    pattern = rf"{re.escape(label)}\s*[:\-]\s*([^\n\r]+)"
    match = re.search(pattern, response, flags=re.IGNORECASE)
    return match.group(1).strip()[:120] if match else None


@ai_bp.route('/crm-agent', methods=['GET', 'POST'])
@login_required
def crm_agent():
    if not _require_ai_permission('ai-crm-agent'):
        return redirect(url_for('ai.dashboard'))
    setting = get_setting(); result = None; log = None
    inquiries = SalesInquiry.query.order_by(SalesInquiry.created_at.desc()).limit(150).all()
    selected_inquiry_id = request.values.get('inquiry_id') or ''
    inquiry = SalesInquiry.query.get(selected_inquiry_id) if selected_inquiry_id else None
    context_data = _crm_inquiry_context(inquiry) if inquiry else ''
    default_prompt = _crm_agent_prompt()
    if request.method == 'POST':
        inquiry = SalesInquiry.query.get(request.form.get('inquiry_id')) if request.form.get('inquiry_id') else None
        if not inquiry:
            flash('Please select a CRM inquiry/lead.', 'danger')
        else:
            context_data = _crm_inquiry_context(inquiry)
            prompt = request.form.get('prompt') or default_prompt
            response, error = call_ai(setting, prompt, context_data=context_data)
            log = save_log('AI CRM Agent', prompt, response, context_data=context_data, related_module='Sales Inquiry', related_ref=inquiry.ref_no, error=error)
            result = response
            if response:
                inquiry.ai_opportunity_score = _extract_value_from_response(response, 'Opportunity Score') or inquiry.ai_opportunity_score
                inquiry.ai_lead_temperature = _extract_value_from_response(response, 'Lead Temperature') or inquiry.ai_lead_temperature
                inquiry.ai_followup_text = response
                inquiry.ai_recommended_action = _extract_value_from_response(response, 'Recommended Next Action') or inquiry.ai_recommended_action
                inquiry.ai_last_followup = datetime.utcnow()
                db.session.commit()
            flash('AI CRM Agent output generated and saved on inquiry.' if not error else 'AI CRM output saved, but live API returned an error/local response. Check AI Logs.', 'success' if not error else 'warning')
    return render_template('ai/phase16b_crm_agent.html', inquiries=inquiries, selected_inquiry_id=str(selected_inquiry_id), inquiry=inquiry, context_data=context_data, default_prompt=default_prompt, result=result, log=log)


@ai_bp.route('/crm-agent/inquiry/<int:inquiry_id>', methods=['GET', 'POST'])
@login_required
def crm_agent_from_inquiry(inquiry_id):
    if not _require_ai_permission('ai-crm-agent'):
        return redirect(url_for('sales.inquiry_detail', inquiry_id=inquiry_id))
    inquiry = SalesInquiry.query.get_or_404(inquiry_id)
    setting = get_setting(); result = None; log = None
    context_data = _crm_inquiry_context(inquiry)
    default_prompt = _crm_agent_prompt()
    if request.method == 'POST':
        prompt = request.form.get('prompt') or default_prompt
        response, error = call_ai(setting, prompt, context_data=context_data)
        log = save_log('AI CRM Agent', prompt, response, context_data=context_data, related_module='Sales Inquiry', related_ref=inquiry.ref_no, error=error)
        result = response
        if response:
            inquiry.ai_opportunity_score = _extract_value_from_response(response, 'Opportunity Score') or inquiry.ai_opportunity_score
            inquiry.ai_lead_temperature = _extract_value_from_response(response, 'Lead Temperature') or inquiry.ai_lead_temperature
            inquiry.ai_followup_text = response
            inquiry.ai_recommended_action = _extract_value_from_response(response, 'Recommended Next Action') or inquiry.ai_recommended_action
            inquiry.ai_last_followup = datetime.utcnow()
            db.session.commit()
        flash('AI CRM Agent output generated and saved on inquiry.' if not error else 'AI CRM output saved, but live API returned an error/local response. Check AI Logs.', 'success' if not error else 'warning')
    return render_template('ai/phase16b_crm_agent_single.html', inquiry=inquiry, context_data=context_data, default_prompt=default_prompt, result=result, log=log)


@ai_bp.route('/project-manager', methods=['GET', 'POST'])
@login_required
def project_manager():
    if not _require_ai_permission('ai-project-manager'):
        return redirect(url_for('ai.dashboard'))
    setting = get_setting(); result = None; log = None
    projects = Project.query.order_by(Project.created_at.desc()).limit(150).all()
    selected_project_id = request.values.get('project_id') or ''
    project = Project.query.get(selected_project_id) if selected_project_id else None
    context_data = _project_manager_context(project) if project else ''
    default_prompt = _project_manager_prompt()
    if request.method == 'POST':
        project = Project.query.get(request.form.get('project_id')) if request.form.get('project_id') else None
        if not project:
            flash('Please select a project.', 'danger')
        else:
            context_data = _project_manager_context(project)
            prompt = request.form.get('prompt') or default_prompt
            response, error = call_ai(setting, prompt, context_data=context_data)
            log = save_log('AI Project Manager', prompt, response, context_data=context_data, related_module='Project', related_ref=project.project_name, error=error)
            result = response
            if response:
                project.ai_health_score = _extract_value_from_response(response, 'Project Health Score') or project.ai_health_score
                project.ai_risk_level = _extract_value_from_response(response, 'Risk Level') or project.ai_risk_level
                project.ai_delay_prediction = _extract_value_from_response(response, 'Delay Prediction') or project.ai_delay_prediction
                project.ai_project_summary = response
                project.ai_recommended_actions = _extract_value_from_response(response, 'Recommended Actions') or project.ai_recommended_actions
                project.ai_last_analysis = datetime.utcnow()
                db.session.commit()
            flash('AI Project Manager analysis generated and saved on project.' if not error else 'AI Project Manager output saved, but live API returned an error/local response. Check AI Logs.', 'success' if not error else 'warning')
    return render_template('ai/phase16b_project_manager.html', projects=projects, selected_project_id=str(selected_project_id), project=project, context_data=context_data, default_prompt=default_prompt, result=result, log=log)


@ai_bp.route('/project-manager/project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def project_manager_from_project(project_id):
    if not _require_ai_permission('ai-project-manager'):
        return redirect(url_for('projects.detail', project_id=project_id))
    project = Project.query.get_or_404(project_id)
    setting = get_setting(); result = None; log = None
    context_data = _project_manager_context(project)
    default_prompt = _project_manager_prompt()
    if request.method == 'POST':
        prompt = request.form.get('prompt') or default_prompt
        response, error = call_ai(setting, prompt, context_data=context_data)
        log = save_log('AI Project Manager', prompt, response, context_data=context_data, related_module='Project', related_ref=project.project_name, error=error)
        result = response
        if response:
            project.ai_health_score = _extract_value_from_response(response, 'Project Health Score') or project.ai_health_score
            project.ai_risk_level = _extract_value_from_response(response, 'Risk Level') or project.ai_risk_level
            project.ai_delay_prediction = _extract_value_from_response(response, 'Delay Prediction') or project.ai_delay_prediction
            project.ai_project_summary = response
            project.ai_recommended_actions = _extract_value_from_response(response, 'Recommended Actions') or project.ai_recommended_actions
            project.ai_last_analysis = datetime.utcnow()
            db.session.commit()
        flash('AI Project Manager analysis generated and saved on project.' if not error else 'AI Project Manager output saved, but live API returned an error/local response. Check AI Logs.', 'success' if not error else 'warning')
    return render_template('ai/phase16b_project_manager_single.html', project=project, context_data=context_data, default_prompt=default_prompt, result=result, log=log)


@ai_bp.route('/settings', methods=['GET','POST'])
@login_required
def settings():
    if current_user.role != 'Admin':
        flash('Only admin can change AI settings.', 'danger')
        return redirect(url_for('ai.dashboard'))
    setting = get_setting()
    test_result = None
    test_error = None
    if request.method == 'POST':
        setting.enabled = request.form.get('enabled') == 'on'
        setting.provider = request.form.get('provider') or 'OpenAI Responses API'
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
        db.session.commit()

        if request.form.get('action') == 'test':
            test_result, test_error = test_ai_connection(setting)
            if test_error:
                flash('AI settings saved, but API test returned an error. See the test box below.', 'warning')
            else:
                flash('AI settings saved and API connection tested successfully.', 'success')
            masked_key = 'Saved / Environment Key Available' if get_api_key(setting) else 'Use OPENAI_API_KEY environment variable or enter key'
            return render_template('ai/settings.html', setting=setting, masked_key=masked_key, test_result=test_result, test_error=test_error)

        flash('AI settings saved.', 'success')
        return redirect(url_for('ai.settings'))

    masked_key = 'Saved / Environment Key Available' if get_api_key(setting) else 'Use OPENAI_API_KEY environment variable or enter key'
    return render_template('ai/settings.html', setting=setting, masked_key=masked_key, test_result=test_result, test_error=test_error)
