from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import AuditLog, ApprovalHistory

activity_bp = Blueprint("activity", __name__, url_prefix="/activity")

@activity_bp.route("/")
@login_required
def activity_log():
    module = request.args.get("module", "").strip()
    action = request.args.get("action", "").strip()
    query = AuditLog.query
    if module:
        query = query.filter(AuditLog.module.ilike(f"%{module}%"))
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    activities = query.order_by(AuditLog.created_at.desc()).limit(200).all()
    histories = ApprovalHistory.query.order_by(ApprovalHistory.reviewed_at.desc()).limit(100).all()
    return render_template("activity/log.html", activities=activities, histories=histories, selected_module=module, selected_action=action)
