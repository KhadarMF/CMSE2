from flask import request, redirect, url_for, flash, session
from flask_login import current_user
from app.permissions import can_access_module

# Phase 15M - Full permission enforcement.
# Every non-auth route must be mapped or denied for non-admin users.

ADMIN_ENDPOINT_KEYS = {
    "admin.settings_home": "admin-settings",
    "admin.test_email": "admin-settings",
    "admin.company_profile": "company-profile",
    "admin.branches": "branches",
    "admin.toggle_branch": "branches",
    "admin.departments": "departments",
    "admin.toggle_department": "departments",
    "admin.permissions_overview": "user-form-permissions",
    "admin.form_permissions": "user-form-permissions",
    "admin.permission_inspector": "user-form-permissions",
    "admin.backup_home": "backup",
    "admin.create_backup": "backup",
    "admin.download_backup": "backup",
    "activity.activity_log": "activity-log",
    "users.list_users": "users",
    "users.create_user": "users",
    "users.edit_user": "users",
    "users.change_password": "users",
    "users.toggle_user": "users",
}

ENDPOINT_KEYS = {
    # Projects
    "projects.list_projects": "projects",
    "projects.detail": "projects",
    "projects.create_project": "projects",
    "projects.edit_project": "projects",
    # Project Tasks
    "project_tasks.list_tasks": "project-tasks",
    "project_tasks.create_task": "project-tasks",
    "project_tasks.edit_task": "project-tasks",
    "project_tasks.delete_task": "project-tasks",
    "project_tasks.employee_report": "project-tasks",
    "tasks.my_tasks": "project-tasks",
    # Issues
    "issues.list_issues": "issues-risks",
    "issues.create_issue": "issues-risks",
    "issues.edit_issue": "issues-risks",
    "issues.delete_issue": "issues-risks",
    # Documents
    "documents.list_documents": "documents",
    "documents.upload_document": "documents",
    "documents.detail": "documents",
    "documents.new_version": "documents",
    "documents.review_document": "documents",
    "documents.download_document": "documents",
    "documents.download_version": "documents",
    # Materials
    "materials.dashboard": "materials",
    "materials.items": "material-items",
    "materials.create_item": "material-items",
    "materials.requests_list": "material-request",
    "materials.create_request": "material-request",
    "materials.request_detail": "material-request",
    "materials.issue_from_request": "material-issue",
    "materials.issues_list": "material-issue",
    "materials.issue_detail": "material-issue",
    "materials.create_return": "material-return",
    "materials.returns_list": "material-return",
    "materials.return_detail": "material-return",
    "materials.material_reports": "material-reports",
    "materials.project_material_report": "material-reports",
    # Sales CRM
    "sales.dashboard": "sales-crm",
    "sales.inquiries": "customer-inquiry",
    "sales.create_inquiry": "customer-inquiry",
    "sales.inquiry_detail": "customer-inquiry",
    "sales.quotations": "quotation",
    "sales.create_quotation": "quotation",
    "sales.quotation_detail": "quotation",
    "sales.quotation_pdf": "quotation",
    "sales.send_quotation_whatsapp": "quotation",
    "sales.quotation_items": "quotation-items",
    "sales.quotation_items_template": "quotation-items",
    # Support
    "support.dashboard": "after-sales",
    "support.warranties": "warranty",
    "support.create_warranty": "warranty",
    "support.warranty_detail": "warranty",
    "support.tickets": "service-ticket",
    "support.create_ticket": "service-ticket",
    "support.ticket_detail": "service-ticket",
    "support.update_ticket": "service-ticket",
    "support.add_visit": "service-ticket",
    "support.ticket_report": "service-ticket",
    "support.ticket_pdf": "service-ticket",
    # Notifications
    "notifications.list_notifications": "notifications",
    "notifications.create_notification": "notifications",
    "notifications.mark_read": "notifications",
    "notifications.logs": "notification-log",
    "notifications.send_email_log": "notification-log",
    "notifications.sms_queue": "sms-queue",
    "notifications.create_sms_queue": "sms-queue",
    "notifications.mark_sms_sent": "sms-queue",
    "notifications.whatsapp_settings": "whatsapp-integration",
    "whatsapp.test_send": "whatsapp-integration",
    "whatsapp.messages": "whatsapp-integration",
    "whatsapp.message_detail": "whatsapp-integration",
    "whatsapp.resend_message": "whatsapp-integration",
    "whatsapp.conversations": "whatsapp-integration",
    "whatsapp.conversation_detail": "whatsapp-integration",
    "whatsapp.mark_conversation_read": "whatsapp-integration",
    "whatsapp.retry_failed_conversation": "whatsapp-integration",
    "whatsapp.unread_count": "whatsapp-integration",
    "whatsapp.health": "whatsapp-integration",
    # Production
    "production.readiness": "production-readiness",
    # AI
    "ai.dashboard": "ai-assistant",
    "ai.assistant": "ai-assistant",
    "ai.service_ticket_helper": "ai-assistant",
    "ai.crm_helper": "ai-assistant",
    "ai.reports": "ai-reports",
    "ai.logs": "ai-logs",
    "ai.update_log_status": "ai-logs",
    "ai.settings": "ai-settings",
    # Reports
    "reports.reports_home": "reports",
    "reports.project_report": "project-reports",
    "reports.project_report_pdf": "project-reports",
    "reports.project_full_report": "project-reports",
    "reports.project_full_report_pdf": "project-reports",
    "reports.customer_reports": "customer-reports",
    "reports.customer_report_detail": "customer-reports",
    "reports.customer_report_pdf": "customer-reports",
    "reports.form_pdf": "form-reports",
    # Master Data
    "master.customers": "customers",
    "master.create_customer": "customers",
    "master.customer_360": "customers",
    "master.edit_customer": "customers",
    "master.employees": "employees",
    "master.create_employee": "employees",
    "master.edit_employee": "employees",
    "master.teams": "teams",
    "master.create_team": "teams",
    "master.team_detail": "teams",
    "master.edit_team": "teams",
    "master.add_team_member": "teams",
    "master.remove_team_member": "teams",
    "master.project_workforce": "project-workforce",
    "master.remove_project_team": "project-workforce",
    "master.remove_project_employee": "project-workforce",
    # Payroll
    "payroll.dashboard": "payroll",
    "payroll.batches": "payroll",
    "payroll.create_batch": "payroll",
    "payroll.batch_detail": "payroll",
    "payroll.approve_batch": "payroll",
    "payroll.entries": "payroll",
    "payroll.entry_detail": "payroll",
    "payroll.add_payment": "payroll",
    "payroll.employee_statement": "payroll",
    "payroll.project_payroll": "payroll",
}

BLUEPRINT_FALLBACK_KEYS = {
    "projects": "projects", "project_tasks": "project-tasks", "tasks": "project-tasks",
    "issues": "issues-risks", "documents": "documents", "materials": "materials",
    "sales": "sales-crm", "support": "after-sales", "notifications": "notifications",
    "production": "production-readiness", "ai": "ai-assistant", "reports": "reports",
    "master": "customers", "payroll": "payroll", "admin": "admin-settings", "users": "users",
    "activity": "activity-log",
}

ACTION_WORDS = {
    "create": "create", "new": "create", "add": "create", "upload": "create",
    "edit": "edit", "update": "edit", "toggle": "edit", "status": "edit", "read": "edit",
    "delete": "delete", "remove": "delete",
    "review": "approve", "approve": "approve",
    "pdf": "print_export", "print": "print_export", "download": "print_export", "template": "print_export", "report": "print_export",
}

READ_ONLY_ENDPOINTS = {"dashboard.dashboard"}
PUBLIC_PREFIXES = (
    "static",
    "auth",
    "health",
    "whatsapp.webhook_verify",
    "whatsapp.webhook_receive",
    "sales.public_quotation_short",
    "sales.public_quotation_short_pdf",
    "sales.public_quotation",
)


def action_for_endpoint(endpoint, method):
    if method == "POST":
        if any(w in endpoint for w in ["delete", "remove"]): return "delete"
        if any(w in endpoint for w in ["review", "approve"]): return "approve"
        if any(w in endpoint for w in ["create", "new", "add", "upload"]): return "create"
        if any(w in endpoint for w in ["edit", "update", "toggle", "status", "read"]): return "edit"
    for word, action in ACTION_WORDS.items():
        if word in endpoint:
            return action
    return "view"


def register_permission_enforcer(app):
    @app.before_request
    def enforce_user_permissions():
        endpoint = request.endpoint or ""
        if not endpoint:
            return None
        blueprint = endpoint.split(".")[0]
        # Phase 17B.1D Security Hotfix:
        # Authentication is enforced globally here as a safety net.
        # Some routes may accidentally miss @login_required, so no internal ERP
        # endpoint should be reachable unless the user is authenticated.
        # Public endpoints are limited to auth pages, static assets, health checks,
        # WhatsApp webhook, and signed public quotation links.
        if endpoint.startswith(PUBLIC_PREFIXES):
            return None
        if (not current_user.is_authenticated) or (session.get("cmse_logged_in") is not True):
            flash("Please login to continue.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if str(getattr(current_user, "role", "") or "").strip().lower() == "admin":
            return None
        if endpoint in READ_ONLY_ENDPOINTS:
            return None

        # Forms are controlled by form_key in URL.
        if blueprint == "forms":
            if endpoint == "forms.forms_home":
                key, action = "forms-home", "view"
            else:
                key = request.view_args.get("form_key") if request.view_args else None
                if not key:
                    key, action = "forms-home", "view"
                elif endpoint == "forms.create_form":
                    action = "create"
                elif endpoint == "forms.edit_form":
                    action = "edit"
                elif endpoint == "forms.delete_form":
                    action = "delete"
                elif endpoint == "forms.review_form":
                    action = "approve"
                elif endpoint == "forms.print_form":
                    action = "print_export"
                elif endpoint == "forms.submit_form":
                    action = "edit"
                else:
                    action = "view"
        else:
            key = ADMIN_ENDPOINT_KEYS.get(endpoint) or ENDPOINT_KEYS.get(endpoint) or BLUEPRINT_FALLBACK_KEYS.get(blueprint)
            action = action_for_endpoint(endpoint, request.method)

        # Security rule: unknown protected endpoint is denied to non-admin.
        if not key:
            flash("Access Denied: This page has no permission mapping. Contact admin.", "danger")
            return redirect(url_for("dashboard.dashboard"))

        if not can_access_module(current_user, key, action):
            flash(f"Access Denied: You do not have permission for {key} ({action}).", "danger")
            return redirect(url_for("dashboard.dashboard"))
        return None
