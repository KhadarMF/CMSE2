import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import Project, Document, DocumentVersion, DOCUMENT_TYPES, APPROVAL_STATUSES
from app.permissions import can_upload_document, can_review_document
from app.activity import log_activity, log_approval
from app.notifications import notify_roles, notify_user

document_bp = Blueprint('documents', __name__, url_prefix='/documents')
ALLOWED_EXTENSIONS={'pdf','doc','docx','xls','xlsx','jpg','jpeg','png'}
def allowed_file(fn): return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS
def save_file(file):
    orig=secure_filename(file.filename); stored=f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{orig}"; file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], stored)); return orig,stored
@document_bp.route('/')
@login_required
def list_documents():
    status_filter=request.args.get('status',''); project_filter=request.args.get('project_id',''); search=request.args.get('search','').strip(); q=Document.query
    if status_filter: q=q.filter_by(approval_status=status_filter)
    if project_filter: q=q.filter_by(project_id=project_filter)
    if search:
        like=f'%{search}%'; q=q.filter((Document.document_title.ilike(like)) | (Document.document_type.ilike(like)))
    return render_template('documents/list.html', documents=q.order_by(Document.upload_date.desc()).all(), projects=Project.query.order_by(Project.project_name.asc()).all(), statuses=APPROVAL_STATUSES, selected_status=status_filter, selected_project=project_filter, search=search)
@document_bp.route('/upload', methods=['GET','POST'])
@login_required
def upload_document():
    if not can_upload_document(current_user): flash('You do not have permission to upload documents.','danger'); return redirect(url_for('documents.list_documents'))
    projects=Project.query.order_by(Project.project_name.asc()).all()
    if request.method=='POST':
        file=request.files.get('file')
        if not file or file.filename=='': flash('Please select a file.','danger'); return redirect(request.url)
        if not allowed_file(file.filename): flash('File type not allowed.','danger'); return redirect(request.url)
        orig,stored=save_file(file)
        doc=Document(project_id=request.form.get('project_id'), document_title=request.form.get('document_title'), document_type=request.form.get('document_type'), uploaded_by_id=current_user.id, file_name=orig, stored_file_name=stored, remarks=request.form.get('remarks'), approval_status=request.form.get('approval_status','Draft'))
        db.session.add(doc); db.session.flush(); db.session.add(DocumentVersion(document_id=doc.id, version_number=1, file_name=orig, stored_file_name=stored, uploaded_by_id=current_user.id, remarks='Initial upload'))
        log_activity('Upload','Document',doc.id,f'Uploaded document: {doc.document_title}')
        if doc.approval_status=='Submitted': notify_roles(['Admin','Management','Operation Manager'], 'Document submitted for approval', f"{current_user.full_name} submitted document '{doc.document_title}' for approval.", 'Document', doc.id)
        db.session.commit(); flash('Document uploaded successfully.','success'); return redirect(url_for('documents.list_documents'))
    return render_template('documents/upload.html', projects=projects, document_types=DOCUMENT_TYPES, statuses=APPROVAL_STATUSES)
@document_bp.route('/<int:document_id>')
@login_required
def detail(document_id):
    doc=Document.query.get_or_404(document_id); versions=DocumentVersion.query.filter_by(document_id=doc.id).order_by(DocumentVersion.version_number.desc()).all(); return render_template('documents/detail.html', document=doc, versions=versions)
@document_bp.route('/<int:document_id>/new-version', methods=['GET','POST'])
@login_required
def new_version(document_id):
    doc=Document.query.get_or_404(document_id)
    if request.method=='POST':
        file=request.files.get('file')
        if not file or file.filename=='': flash('Please select a file.','danger'); return redirect(request.url)
        if not allowed_file(file.filename): flash('File type not allowed.','danger'); return redirect(request.url)
        orig,stored=save_file(file); latest=DocumentVersion.query.filter_by(document_id=doc.id).order_by(DocumentVersion.version_number.desc()).first(); nxt=(latest.version_number+1) if latest else 1
        db.session.add(DocumentVersion(document_id=doc.id, version_number=nxt, file_name=orig, stored_file_name=stored, uploaded_by_id=current_user.id, remarks=request.form.get('remarks')))
        doc.file_name=orig; doc.stored_file_name=stored; doc.approval_status='Draft'; doc.manager_comments=None
        log_activity('New Version','Document',doc.id,f'Uploaded version {nxt} for document: {doc.document_title}')
        db.session.commit(); flash('New document version uploaded successfully.','success'); return redirect(url_for('documents.detail', document_id=doc.id))
    return render_template('documents/new_version.html', document=doc)
@document_bp.route('/<int:document_id>/review', methods=['GET','POST'])
@login_required
def review_document(document_id):
    doc=Document.query.get_or_404(document_id)
    if not can_review_document(current_user): flash('Only Admin, Management, or Operation Manager can review documents.','danger'); return redirect(url_for('documents.detail', document_id=doc.id))
    if request.method=='POST':
        new_status=request.form.get('approval_status')
        if new_status not in ['Under Review','Approved','Rejected','Need Correction']: flash('Invalid review status.','danger'); return redirect(request.url)
        prev=doc.approval_status; doc.approval_status=new_status; doc.manager_comments=request.form.get('manager_comments'); doc.reviewed_by_id=current_user.id; doc.reviewed_at=datetime.utcnow()
        log_approval('Document',doc.id,prev,new_status,doc.manager_comments); log_activity('Review','Document',doc.id,f'Changed document status from {prev} to {new_status}')
        notify_user(doc.uploader, f'Document {new_status}', f"Your document '{doc.document_title}' has been marked as {new_status}. Comments: {doc.manager_comments or ''}", 'Document', doc.id)
        db.session.commit(); flash('Document review saved.','success'); return redirect(url_for('documents.detail', document_id=doc.id))
    return render_template('documents/review.html', document=doc)
@document_bp.route('/download/<int:document_id>')
@login_required
def download_document(document_id):
    doc=Document.query.get_or_404(document_id); return send_from_directory(current_app.config['UPLOAD_FOLDER'], doc.stored_file_name, as_attachment=True, download_name=doc.file_name)
@document_bp.route('/version/<int:version_id>/download')
@login_required
def download_version(version_id):
    v=DocumentVersion.query.get_or_404(version_id); return send_from_directory(current_app.config['UPLOAD_FOLDER'], v.stored_file_name, as_attachment=True, download_name=v.file_name)
