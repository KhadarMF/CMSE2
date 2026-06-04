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
    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"]) as smtp:
        if cfg["MAIL_USE_TLS"]:
            smtp.starttls()
        smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        smtp.send_message(msg)

def create_notification(to_user=None, to_email=None, subject="", message="", module=None, record_id=None, send_now=True):
    recipient_email = to_email or (to_user.email if to_user else None)
    notification = Notification(recipient_user_id=to_user.id if to_user else None, recipient_email=recipient_email, subject=subject, message=message, module=module, record_id=record_id, status="Pending")
    db.session.add(notification)
    db.session.flush()
    if send_now and recipient_email:
        try:
            send_email(recipient_email, subject, message)
            notification.status = "Sent"
            notification.sent_at = datetime.utcnow()
        except Exception as e:
            notification.status = "Failed"
            notification.error_message = str(e)
    return notification

def notify_roles(roles, subject, message, module=None, record_id=None):
    users = User.query.filter(User.role.in_(roles), User.is_active == True).all()
    for user in users:
        create_notification(user, subject=subject, message=message, module=module, record_id=record_id)
    return users

def notify_user(user, subject, message, module=None, record_id=None):
    if user:
        return create_notification(user, subject=subject, message=message, module=module, record_id=record_id)
    return None
