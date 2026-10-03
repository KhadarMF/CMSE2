import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from app import db
from app.models import Notification, User
from app.settings import get_email_config

def email_is_configured():
    cfg = get_email_config()
    return bool(cfg["MAIL_SERVER"] and cfg["MAIL_USERNAME"] and cfg["MAIL_PASSWORD"] and cfg["MAIL_DEFAULT_SENDER"])

def send_email(to_email, subject, message):
    cfg = get_email_config()
    if not email_is_configured():
        raise RuntimeError("Email SMTP settings are not configured.")
    msg = MIMEText(message, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg["MAIL_DEFAULT_SENDER"]
    msg["To"] = to_email
    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as smtp:
        if cfg["MAIL_USE_TLS"]:
            smtp.starttls()
        smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        smtp.send_message(msg)

def create_notification(to_user=None, to_email=None, subject="", message="", module=None, record_id=None, send_now=True):
    recipient_email = to_email or (to_user.email if to_user else None)
    notification = Notification(recipient_user_id=to_user.id if to_user else None, recipient_email=recipient_email, subject=subject, message=message, module=module, record_id=record_id, status="Pending")
    db.session.add(notification)
    db.session.flush()
    if to_user and to_user.is_active:
        from app.notification_gateway import create_notification_event
        create_notification_event(subject, message, target_user=to_user,
            related_module=module, related_ref=str(record_id) if record_id is not None else None,
            send_email_now=send_now, notification_ref=f"WORKFLOW-{notification.id}")
        notification.status = "Queued" if send_now else "Skipped"
    elif recipient_email and to_user is None and send_now:
        from app.models import NotificationLog
        from app.notification_delivery import queue_email
        log = NotificationLog(notification_ref=f"WORKFLOW-{notification.id}", channel="Email",
            recipient=recipient_email, subject=subject, message=message, status="Queued")
        db.session.add(log)
        queue_email(log)
    else:
        notification.status = "Skipped"
    return notification

def notify_roles(roles, subject, message, module=None, record_id=None):
    users = User.query.filter(User.role.in_(roles), User.is_active == True).all()
    for user in users:
        create_notification(user, subject=subject, message=message, module=module, record_id=record_id)
    return users

def notify_user(user, subject, message, module=None, record_id=None):
    if user and user.is_active:
        return create_notification(user, subject=subject, message=message, module=module, record_id=record_id)
    return None


def notify_approvers(form_key, subject, message, record_id, exclude_user_id=None):
    from app.permissions import can_access_module
    users = User.query.filter_by(is_active=True).all()
    recipients = [user for user in users if user.id != exclude_user_id
                  and can_access_module(user, form_key, "approve")]
    for user in recipients:
        notify_user(user, subject, message, module=form_key, record_id=record_id)
    return recipients
