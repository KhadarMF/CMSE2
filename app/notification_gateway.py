from datetime import datetime
from app import db
from app.models import SystemNotification, NotificationLog, SMSQueue, User, Employee
from app.notifications import send_email

def _ref(prefix):
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:17]}"

def _user_phone(user):
    if not user:
        return None
    try:
        emp = Employee.query.filter_by(user_id=user.id).first()
        if emp and emp.phone:
            return emp.phone
    except Exception:
        pass
    return None

def create_notification_event(title, message, target_user=None, priority='Medium', category='General', related_module=None, related_ref=None, send_email_now=False, queue_sms=False, created_by_id=None):
    note = SystemNotification(ref_no=_ref('NOT'), title=title, message=message, category=category, priority=priority, target_user_id=(target_user.id if target_user else None), related_module=related_module, related_ref=related_ref)
    db.session.add(note)
    db.session.flush()
    recipient_name = target_user.full_name if target_user else 'All Users'
    # In-app log
    db.session.add(NotificationLog(notification_ref=note.ref_no, recipient_user_id=(target_user.id if target_user else None), recipient_name=recipient_name, channel='In-App', recipient=recipient_name, subject=title, message=message, related_module=related_module, related_ref=related_ref, status='Sent', sent_at=datetime.utcnow(), created_by_id=created_by_id))
    # Email log and optional send
    if target_user and getattr(target_user, 'email', None):
        elog = NotificationLog(notification_ref=note.ref_no, recipient_user_id=target_user.id, recipient_name=target_user.full_name, channel='Email', recipient=target_user.email, subject=title, message=message, related_module=related_module, related_ref=related_ref, status='Pending', created_by_id=created_by_id)
        db.session.add(elog)
        db.session.flush()
        if send_email_now:
            try:
                send_email(target_user.email, title, message)
                elog.status='Sent'; elog.sent_at=datetime.utcnow()
            except Exception as e:
                elog.status='Failed'; elog.error_message=str(e)
        else:
            elog.status='Queued'
    # SMS queue only, no API needed
    phone = _user_phone(target_user)
    if queue_sms and phone:
        sms = SMSQueue(ref_no=_ref('SMS'), recipient_name=target_user.full_name, phone_number=phone, message=message, related_module=related_module, related_ref=related_ref, status='Pending', created_by_id=created_by_id)
        db.session.add(sms)
        db.session.add(NotificationLog(notification_ref=note.ref_no, recipient_user_id=target_user.id, recipient_name=target_user.full_name, channel='SMS', recipient=phone, subject=title, message=message, related_module=related_module, related_ref=related_ref, status='Queued', created_by_id=created_by_id))
    return note