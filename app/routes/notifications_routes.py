from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, SystemNotification, NotificationLog, SMSQueue, WhatsAppIntegrationSetting, NOTIFICATION_CHANNELS, NOTIFICATION_DELIVERY_STATUSES, TICKET_PRIORITIES
from app.notification_gateway import create_notification_event
from app.notification_delivery import deliver_email
from app.permissions import can_access_module

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

def make_ref(prefix):
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:17]}"

@notifications_bp.before_app_request
def ensure_notification_tables():
    # Phase 20D: db.create_all() removed - the schema is owned by Alembic
    # (`flask db upgrade`). create_all() only ever created MISSING TABLES;
    # it silently ignored new COLUMNS, which is how the schema drifted.
    return None

def _admin():
    return (current_user.role or '').strip().lower() == 'admin'


def _inbox():
    return SystemNotification.query.filter_by(target_user_id=current_user.id)


def _log_scope(query):
    if not _admin():
        query = query.filter((NotificationLog.recipient_user_id == current_user.id) |
                             (NotificationLog.created_by_id == current_user.id))
    return query


@notifications_bp.route('/')
@login_required
def list_notifications():
    query = SystemNotification.query if _admin() and request.args.get('all') == '1' else _inbox()
    notes = query.order_by(SystemNotification.created_at.desc(), SystemNotification.id.desc()).limit(500).all()
    unread = _inbox().filter_by(status='Unread').count()
    latest = _inbox().order_by(SystemNotification.id.desc()).first()
    return render_template('notifications/list.html', notifications=notes, unread=unread, latest_id=latest.id if latest else 0)


@notifications_bp.route('/unread-count')
@login_required
def unread_count():
    latest = _inbox().order_by(SystemNotification.id.desc()).first()
    response = jsonify(unread=_inbox().filter_by(status='Unread').count(), latest_id=latest.id if latest else 0)
    response.headers['Cache-Control'] = 'no-store'
    return response


@notifications_bp.route('/create', methods=['GET','POST'])
@login_required
def create_notification():
    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    if request.method == 'POST':
        raw_id = (request.form.get('target_user_id') or '').strip()
        target_user = next((u for u in users if str(u.id) == raw_id), None) if raw_id else None
        title = (request.form.get('title') or '').strip()
        message = (request.form.get('message') or '').strip()
        priority = request.form.get('priority') or 'Medium'
        error = None
        if raw_id and target_user is None:
            error = 'Select an existing active recipient. Nothing was sent.'
        elif not title or len(title) > 180 or not message:
            error = 'Enter a title (up to 180 characters) and a message.'
        elif priority not in TICKET_PRIORITIES:
            error = 'Select a valid priority.'
        elif not users:
            error = 'No active recipients are available.'
        if error:
            flash(error, 'danger')
            return render_template('notifications/form.html', users=users, priorities=TICKET_PRIORITIES), 400
        send_email_now = request.form.get('send_email_now') == 'on'
        queue_sms = request.form.get('queue_sms') == 'on'
        create_notification_event(title, message, target_user=target_user, priority=priority,
            category=(request.form.get('category') or '')[:100],
            related_module=(request.form.get('related_module') or '')[:100],
            related_ref=(request.form.get('related_ref') or '')[:120],
            send_email_now=send_email_now, queue_sms=queue_sms, created_by_id=current_user.id)
        db.session.commit()
        count = 1 if target_user else len(users)
        flash(f'In-app notification delivered to {count} active recipient(s).', 'success')
        if send_email_now:
            flash('Email delivery is attempted separately. Check Notification Log for Sent or Failed.', 'info')
        if queue_sms:
            flash('SMS is queued only; no SMS API is connected. Missing phone numbers appear as Failed in the log.', 'warning')
        return redirect(url_for('notifications.logs') if can_access_module(current_user, 'notification-log') else url_for('notifications.list_notifications'))
    return render_template('notifications/form.html', users=users, priorities=TICKET_PRIORITIES)

@notifications_bp.route('/<int:notification_id>/read', methods=["POST"])
@login_required
def mark_read(notification_id):
    n=SystemNotification.query.get_or_404(notification_id)
    if n.target_user_id != current_user.id:
        abort(403)
    if n.status != 'Read':
        n.status='Read'; n.read_at=datetime.utcnow(); db.session.commit()
    return redirect(url_for('notifications.list_notifications'))

@notifications_bp.route('/logs')
@login_required
def logs():
    channel=request.args.get('channel')
    status=request.args.get('status')
    query=_log_scope(NotificationLog.query)
    if channel: query=query.filter_by(channel=channel)
    if status: query=query.filter_by(status=status)
    logs=query.order_by(NotificationLog.created_at.desc()).limit(500).all()
    return render_template('notifications/logs.html', logs=logs, channels=NOTIFICATION_CHANNELS, statuses=NOTIFICATION_DELIVERY_STATUSES, filters=request.args)

@notifications_bp.route('/email/send/<int:log_id>', methods=["POST"])
@login_required
def send_email_log(log_id):
    log = _log_scope(NotificationLog.query).filter_by(id=log_id).first_or_404()
    if log.channel != 'Email':
        abort(400)
    result = deliver_email(log.id, retry_failed=True)
    if result == 'Sent':
        flash('Email accepted by SMTP.', 'success')
    elif result == 'Failed':
        flash('Email failed. Check the delivery log for the reason.', 'danger')
    else:
        flash('No duplicate email sent. This delivery is already sent or in progress.', 'info')
    return redirect(url_for('notifications.logs', channel='Email'))

@notifications_bp.route('/sms-queue')
@login_required
def sms_queue():
    status=request.args.get('status')
    query=SMSQueue.query
    if not _admin(): query=query.filter_by(created_by_id=current_user.id)
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

@notifications_bp.route('/sms-queue/<int:sms_id>/sent', methods=["POST"])
@login_required
def mark_sms_sent(sms_id):
    sms=SMSQueue.query.get_or_404(sms_id)
    if not _admin() and sms.created_by_id != current_user.id:
        abort(403)
    sms.status='Sent'; sms.sent_at=datetime.utcnow(); sms.provider_response='Marked sent manually - no API connected.'
    NotificationLog.query.filter_by(channel='SMS', notification_ref=sms.ref_no).update(dict(status='Sent', sent_at=sms.sent_at, provider_response=sms.provider_response))
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
