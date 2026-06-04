from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import User, SystemNotification, NotificationLog, SMSQueue, WhatsAppIntegrationSetting, NOTIFICATION_CHANNELS, NOTIFICATION_DELIVERY_STATUSES, TICKET_PRIORITIES
from app.notification_gateway import create_notification_event
from app.notifications import send_email

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

def make_ref(prefix):
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:17]}"

@notifications_bp.before_app_request
def ensure_notification_tables():
    try: db.create_all()
    except Exception: pass

@notifications_bp.route('/')
@login_required
def list_notifications():
    show_all=request.args.get('all')=='1'
    query=SystemNotification.query
    if not show_all:
        query=query.filter((SystemNotification.target_user_id==current_user.id) | (SystemNotification.target_user_id==None))
    notes=query.order_by(SystemNotification.created_at.desc()).all()
    unread=SystemNotification.query.filter(SystemNotification.status=='Unread').count()
    return render_template('notifications/list.html', notifications=notes, unread=unread)

@notifications_bp.route('/create', methods=['GET','POST'])
@login_required
def create_notification():
    if request.method=='POST':
        target_user_id=request.form.get('target_user_id') or None
        target_user=User.query.get(target_user_id) if target_user_id else None
        title=request.form.get('title')
        message=request.form.get('message')
        priority=request.form.get('priority') or 'Medium'
        related_module=request.form.get('related_module')
        related_ref=request.form.get('related_ref')
        category=request.form.get('category')
        send_email_now=request.form.get('send_email_now')=='on'
        queue_sms=request.form.get('queue_sms')=='on'
        create_notification_event(title, message, target_user=target_user, priority=priority, category=category, related_module=related_module, related_ref=related_ref, send_email_now=send_email_now, queue_sms=queue_sms, created_by_id=current_user.id)
        db.session.commit(); flash('Notification created and delivery records/logs saved.', 'success')
        return redirect(url_for('notifications.list_notifications'))
    return render_template('notifications/form.html', users=User.query.filter_by(is_active=True).all(), priorities=TICKET_PRIORITIES)

@notifications_bp.route('/<int:notification_id>/read')
@login_required
def mark_read(notification_id):
    n=SystemNotification.query.get_or_404(notification_id)
    n.status='Read'; n.read_at=datetime.utcnow(); db.session.commit()
    return redirect(url_for('notifications.list_notifications'))

@notifications_bp.route('/logs')
@login_required
def logs():
    channel=request.args.get('channel')
    status=request.args.get('status')
    query=NotificationLog.query
    if channel: query=query.filter_by(channel=channel)
    if status: query=query.filter_by(status=status)
    logs=query.order_by(NotificationLog.created_at.desc()).limit(500).all()
    return render_template('notifications/logs.html', logs=logs, channels=NOTIFICATION_CHANNELS, statuses=NOTIFICATION_DELIVERY_STATUSES, filters=request.args)

@notifications_bp.route('/email/send/<int:log_id>')
@login_required
def send_email_log(log_id):
    log=NotificationLog.query.get_or_404(log_id)
    if log.channel!='Email':
        flash('This log is not an email notification.', 'warning'); return redirect(url_for('notifications.logs'))
    try:
        send_email(log.recipient, log.subject or 'Cadceed-Maal ERP Notification', log.message or '')
        log.status='Sent'; log.sent_at=datetime.utcnow(); log.error_message=None
        flash('Email sent successfully.', 'success')
    except Exception as e:
        log.status='Failed'; log.error_message=str(e); flash(f'Email failed: {e}', 'danger')
    db.session.commit()
    return redirect(url_for('notifications.logs', channel='Email'))

@notifications_bp.route('/sms-queue')
@login_required
def sms_queue():
    status=request.args.get('status')
    query=SMSQueue.query
    if status: query=query.filter_by(status=status)
    items=query.order_by(SMSQueue.created_at.desc()).limit(500).all()
    return render_template('notifications/sms_queue.html', items=items, statuses=NOTIFICATION_DELIVERY_STATUSES, filters=request.args)

@notifications_bp.route('/sms-queue/create', methods=['POST'])
@login_required
def create_sms_queue():
    sms=SMSQueue(ref_no=make_ref('SMS'), recipient_name=request.form.get('recipient_name'), phone_number=request.form.get('phone_number'), message=request.form.get('message'), related_module=request.form.get('related_module'), related_ref=request.form.get('related_ref'), created_by_id=current_user.id)
    db.session.add(sms); db.session.add(NotificationLog(notification_ref=sms.ref_no, recipient_name=sms.recipient_name, channel='SMS', recipient=sms.phone_number, subject='Manual SMS Queue', message=sms.message, related_module=sms.related_module, related_ref=sms.related_ref, status='Queued', created_by_id=current_user.id))
    db.session.commit(); flash('SMS added to manual queue. API is not connected yet.', 'success')
    return redirect(url_for('notifications.sms_queue'))

@notifications_bp.route('/sms-queue/<int:sms_id>/sent')
@login_required
def mark_sms_sent(sms_id):
    sms=SMSQueue.query.get_or_404(sms_id)
    sms.status='Sent'; sms.sent_at=datetime.utcnow(); sms.provider_response='Marked sent manually - no API connected.'
    db.session.commit(); flash('SMS marked as sent manually.', 'success')
    return redirect(url_for('notifications.sms_queue'))

@notifications_bp.route('/whatsapp', methods=['GET','POST'])
@login_required
def whatsapp_settings():
    setting=WhatsAppIntegrationSetting.query.first()
    if not setting:
        setting=WhatsAppIntegrationSetting(); db.session.add(setting); db.session.commit()
    if request.method=='POST':
        setting.enabled=request.form.get('enabled')=='on'
        setting.provider=request.form.get('provider')
        setting.business_phone=request.form.get('business_phone')
        setting.phone_number_id=request.form.get('phone_number_id')
        setting.api_base_url=request.form.get('api_base_url')
        setting.template_mode=request.form.get('template_mode')
        setting.notes=request.form.get('notes')
        setting.updated_by_id=current_user.id
        db.session.commit(); flash('WhatsApp future integration settings saved.', 'success')
        return redirect(url_for('notifications.whatsapp_settings'))
    return render_template('notifications/whatsapp.html', setting=setting)