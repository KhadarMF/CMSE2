from datetime import datetime
from uuid import uuid4
from app import db
from app.models import SystemNotification, NotificationLog, SMSQueue, User, Employee
from app.notification_delivery import queue_email


def _ref(prefix):
    return f"{prefix}-{uuid4().hex}"


def create_notification_event(title, message, target_user=None, priority='Medium', category='General', related_module=None, related_ref=None, send_email_now=False, queue_sms=False, created_by_id=None, notification_ref=None):
    """Create one inbox record per active recipient; caller commits the transaction."""
    if target_user is None:
        return [create_notification_event(title, message, user, priority, category,
                related_module, related_ref, send_email_now, queue_sms, created_by_id)
                for user in User.query.filter_by(is_active=True).order_by(User.id).all()]
    if not target_user.is_active:
        raise ValueError('The selected recipient is inactive.')
    note = SystemNotification(ref_no=notification_ref or _ref('NOT'), title=title[:180],
        message=message, category=category, priority=priority, target_user_id=target_user.id,
        related_module=related_module, related_ref=related_ref)
    db.session.add(note)
    db.session.flush()
    common = dict(notification_ref=note.ref_no, recipient_user_id=target_user.id,
        recipient_name=target_user.full_name, subject=title, message=message,
        related_module=related_module, related_ref=related_ref, created_by_id=created_by_id)
    db.session.add(NotificationLog(**common, channel='In-App', recipient=target_user.full_name,
        status='Sent', sent_at=datetime.utcnow()))
    if send_email_now:
        email = (target_user.email or '').strip()
        log = NotificationLog(**common, channel='Email', recipient=email,
            status='Queued' if email else 'Failed',
            error_message=None if email else 'Recipient has no email address.')
        db.session.add(log)
        if email:
            queue_email(log)
    if queue_sms:
        employee = Employee.query.filter_by(user_id=target_user.id).first()
        phone = employee.phone if employee else None
        sms_ref = _ref('SMS')
        if phone:
            db.session.add(SMSQueue(ref_no=sms_ref, recipient_name=target_user.full_name,
                phone_number=phone, message=message, related_module=related_module,
                related_ref=related_ref, status='Queued', created_by_id=created_by_id))
        # The queue reference makes manual status updates traceable to this log.
        db.session.add(NotificationLog(**{**common, 'notification_ref': sms_ref},
            channel='SMS', recipient=phone or '', status='Queued' if phone else 'Failed',
            error_message=None if phone else 'Recipient has no linked employee phone number.'))
    return note
