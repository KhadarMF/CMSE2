from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Project, Document, SiteSurveyForm, LoadAssessmentForm, DailySiteReport, DeliveryNoteForm, TestingForm, CommissioningForm, HandoverForm, ProjectTask, ProjectIssue
from app.permissions import can_review_document

task_bp=Blueprint('tasks',__name__,url_prefix='/tasks')
FORM_ITEMS=[('site-survey','Site Survey Form',SiteSurveyForm),('load-assessment','Load Assessment Form',LoadAssessmentForm),('daily-site-report','Daily Site Report',DailySiteReport),('delivery-note','Delivery Note',DeliveryNoteForm),('testing','Testing Form',TestingForm),('commissioning','Commissioning Form',CommissioningForm),('handover','Handover Form',HandoverForm)]
@task_bp.route('/')
@login_required
def my_tasks():
    my_forms=[]; corrections=[]; submitted=[]; pending_reviews=[]
    for key,title,Model in FORM_ITEMS:
        for e in Model.query.filter_by(created_by_id=current_user.id).order_by(Model.created_at.desc()).limit(20).all():
            item={'form_key':key,'title':title,'entry':e}; my_forms.append(item)
            if e.approval_status in ['Rejected','Need Correction']: corrections.append(item)
            if e.approval_status in ['Submitted','Under Review']: submitted.append(item)
        if can_review_document(current_user):
            for e in Model.query.filter(Model.approval_status.in_(['Submitted','Under Review','Need Correction'])).order_by(Model.created_at.desc()).limit(20).all():
                pending_reviews.append({'form_key':key,'title':title,'entry':e})
    my_documents=Document.query.filter_by(uploaded_by_id=current_user.id).order_by(Document.upload_date.desc()).limit(30).all()
    pending_docs=Document.query.filter(Document.approval_status.in_(['Submitted','Under Review','Need Correction'])).order_by(Document.upload_date.desc()).limit(30).all() if can_review_document(current_user) else []
    assigned_projects=Project.query.filter(Project.assigned_team.ilike(f'%{current_user.full_name}%')).order_by(Project.created_at.desc()).all()
    assigned_project_tasks=ProjectTask.query.filter_by(assigned_to_id=current_user.id).order_by(ProjectTask.due_date.asc().nullslast(), ProjectTask.created_at.desc()).all()
    responsible_issues=ProjectIssue.query.filter_by(responsible_user_id=current_user.id).order_by(ProjectIssue.reported_at.desc()).all()
    return render_template('tasks/my_tasks.html', my_forms=my_forms, corrections=corrections, submitted=submitted, pending_reviews=pending_reviews, my_documents=my_documents, pending_docs=pending_docs, assigned_projects=assigned_projects, assigned_project_tasks=assigned_project_tasks, responsible_issues=responsible_issues)
