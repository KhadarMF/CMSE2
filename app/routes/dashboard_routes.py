from flask import Blueprint, render_template
from flask_login import login_required
from app.models import (
    Project, Document, SiteSurveyForm, LoadAssessmentForm, DailySiteReport,
    DeliveryNoteForm, TestingForm, CommissioningForm, HandoverForm, ProjectTask, ProjectIssue, WhatsAppMessage
)

dashboard_bp = Blueprint("dashboard", __name__)
FORM_MODELS = [SiteSurveyForm, LoadAssessmentForm, DailySiteReport, DeliveryNoteForm, TestingForm, CommissioningForm, HandoverForm]

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    total_projects = Project.query.count()
    completed_projects = Project.query.filter_by(status="Completed").count()
    active_projects = Project.query.filter(Project.status != "Completed").count()
    pending_approvals = Document.query.filter(Document.approval_status.in_(["Submitted", "Under Review", "Need Correction"])).count()
    rejected_documents = Document.query.filter_by(approval_status="Rejected").count()
    recent_documents = Document.query.order_by(Document.upload_date.desc()).limit(8).all()
    total_online_forms = sum(model.query.count() for model in FORM_MODELS)
    pending_form_approvals = sum(model.query.filter(model.approval_status.in_(["Submitted", "Under Review", "Need Correction"])).count() for model in FORM_MODELS)
    approved_forms = sum(model.query.filter_by(approval_status="Approved").count() for model in FORM_MODELS)
    rejected_forms = sum(model.query.filter_by(approval_status="Rejected").count() for model in FORM_MODELS)
    open_tasks = ProjectTask.query.filter(ProjectTask.status.notin_(["Completed", "Cancelled"])).count()
    overdue_tasks = len([t for t in ProjectTask.query.filter(ProjectTask.status.notin_(["Completed", "Cancelled"])).all() if t.is_overdue])
    open_issues = ProjectIssue.query.filter(ProjectIssue.status.notin_(["Resolved", "Closed"])).count()
    critical_issues = ProjectIssue.query.filter(ProjectIssue.severity == "Critical", ProjectIssue.status.notin_(["Resolved", "Closed"])).count()
    upcoming_tasks = ProjectTask.query.filter(ProjectTask.status.notin_(["Completed", "Cancelled"])).order_by(ProjectTask.due_date.asc().nullslast()).limit(8).all()
    whatsapp_unread = WhatsAppMessage.query.filter_by(direction="Inbound", status="Received").count()
    whatsapp_failed = WhatsAppMessage.query.filter_by(status="Failed").count()
    whatsapp_total = WhatsAppMessage.query.count()
    return render_template(
        "dashboard/dashboard.html",
        total_projects=total_projects,
        active_projects=active_projects,
        completed_projects=completed_projects,
        pending_approvals=pending_approvals,
        rejected_documents=rejected_documents,
        recent_documents=recent_documents,
        total_online_forms=total_online_forms,
        pending_form_approvals=pending_form_approvals,
        approved_forms=approved_forms,
        rejected_forms=rejected_forms,
        open_tasks=open_tasks,
        overdue_tasks=overdue_tasks,
        open_issues=open_issues,
        critical_issues=critical_issues,
        upcoming_tasks=upcoming_tasks,
        whatsapp_unread=whatsapp_unread,
        whatsapp_failed=whatsapp_failed,
        whatsapp_total=whatsapp_total,
    )
