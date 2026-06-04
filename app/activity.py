from flask_login import current_user
from app import db
from app.models import AuditLog, ApprovalHistory

def log_activity(action, module, record_id=None, description=None):
    try:
        user_id = current_user.id if current_user and current_user.is_authenticated else None
    except Exception:
        user_id = None
    db.session.add(AuditLog(user_id=user_id, action=action, module=module, record_id=record_id, description=description))

def log_approval(module, record_id, previous_status, new_status, comments=None):
    try:
        user_id = current_user.id if current_user and current_user.is_authenticated else None
    except Exception:
        user_id = None
    db.session.add(ApprovalHistory(module=module, record_id=record_id, previous_status=previous_status, new_status=new_status, comments=comments, reviewed_by_id=user_id))
