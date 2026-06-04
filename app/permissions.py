from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

PROJECT_CREATE_ROLES = ["Admin", "Operation Manager"]
PROJECT_VIEW_ROLES = [
    "Admin", "Management", "Operation Manager", "Technical Engineer",
    "Site Supervisor", "Warehouse Officer", "Transport Officer",
    "Sales Officer", "Finance Officer",
]
DOCUMENT_UPLOAD_ROLES = PROJECT_VIEW_ROLES
APPROVAL_ROLES = ["Admin", "Management", "Operation Manager"]
DELETE_FORM_ROLES = ["Admin", "Management", "Operation Manager"]

FORM_PERMISSION_MAP = {
    "site-survey": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"],
    "load-assessment": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Sales Officer"],
    "projects": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor", "Sales Officer"],
    "project-tasks": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"],
    "issues-risks": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"],
    "materials": ["Admin", "Management", "Operation Manager", "Warehouse Officer"],
    "sales-crm": ["Admin", "Management", "Operation Manager", "Sales Officer"],
    "customer-inquiry": ["Admin", "Management", "Operation Manager", "Sales Officer"],
    "quotation": ["Admin", "Management", "Operation Manager", "Sales Officer"],
    "after-sales": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"],
    "service-ticket": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"],
    "warranty": ["Admin", "Management", "Operation Manager", "Sales Officer", "Technical Engineer"],
    "notifications": ["Admin", "Management", "Operation Manager"],
    "ai-assistant": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Sales Officer"],
    "reports": ["Admin", "Management", "Operation Manager", "Finance Officer"],
    "daily-site-report": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"],
    "delivery-note": ["Admin", "Management", "Operation Manager", "Warehouse Officer", "Transport Officer"],
    "testing": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"],
    "commissioning": ["Admin", "Management", "Operation Manager", "Technical Engineer"],
    "handover": ["Admin", "Management", "Operation Manager", "Technical Engineer", "Site Supervisor"],
}

def roles_required(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard.dashboard"))
            return func(*args, **kwargs)
        return wrapper
    return decorator

def can_create_project(user):
    return user.role in PROJECT_CREATE_ROLES

def can_upload_document(user):
    return user.role in DOCUMENT_UPLOAD_ROLES

def _dynamic_form_permission(user, form_key):
    try:
        from app.models import UserFormPermission
        perm = UserFormPermission.query.filter_by(user_id=user.id, form_key=form_key).first()
        return perm
    except Exception:
        return None

def _user_has_explicit_permissions(user):
    """Return True when admin has created any explicit permission rows for this user.

    Important ERP rule:
    - If a user has explicit User Form Permissions, the system must follow them strictly.
    - Role defaults are only fallback for users with no custom permission setup.
    """
    try:
        from app.models import UserFormPermission
        return UserFormPermission.query.filter_by(user_id=user.id).count() > 0
    except Exception:
        return False

def _permission_allows(perm, action):
    if not perm:
        return False
    if action == "view":
        return bool(perm.can_view or perm.can_create or perm.can_edit or perm.can_approve or getattr(perm, "can_print_export", False))
    if action == "create": return bool(perm.can_create)
    if action == "edit": return bool(perm.can_edit)
    if action == "delete": return bool(perm.can_delete)
    if action == "approve": return bool(perm.can_approve)
    if action in ["print", "export", "print_export"]: return bool(getattr(perm, "can_print_export", False))
    return False

def can_view_form(user, form_key):
    if user.role == "Admin":
        return True
    perm = _dynamic_form_permission(user, form_key)
    if perm:
        return _permission_allows(perm, "view")
    if _user_has_explicit_permissions(user):
        return False
    return user.role in FORM_PERMISSION_MAP.get(form_key, [])

def can_create_form(user, form_key):
    if user.role == "Admin":
        return True
    perm = _dynamic_form_permission(user, form_key)
    if perm:
        return _permission_allows(perm, "create")
    if _user_has_explicit_permissions(user):
        return False
    return user.role in FORM_PERMISSION_MAP.get(form_key, [])

def can_edit_form(user, form_key, entry):
    if user.role in ["Admin", "Management", "Operation Manager"]:
        return True
    perm = _dynamic_form_permission(user, form_key)
    if perm and perm.can_edit:
        return True
    return can_create_form(user, form_key) and entry.created_by_id == user.id

def can_delete_form(user):
    return user.role in DELETE_FORM_ROLES

def can_review_document(user):
    return user.role in APPROVAL_ROLES

def can_manage_users(user):
    return user.role == "Admin"


def can_access_module(user, key, action="view"):
    """Strict generic access helper for modules, reports and extended forms.

    Rules:
    1. Admin always allowed.
    2. If user has explicit permission rows, those rows control access strictly.
       Missing row = denied.
    3. Role fallback applies only when no explicit permission rows exist for the user.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if user.role == "Admin":
        return True
    perm = _dynamic_form_permission(user, key)
    if perm:
        return _permission_allows(perm, action)
    if _user_has_explicit_permissions(user):
        return False
    return user.role in FORM_PERMISSION_MAP.get(key, [])

def permission_required(key, action="view"):
    from functools import wraps
    from flask import flash, redirect, url_for
    from flask_login import current_user
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if not can_access_module(current_user, key, action):
                flash("Access Denied: You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard.dashboard"))
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Phase 15M: STRICT USER PERMISSION OVERRIDES
# ERP rule: Admin decides all non-admin access. Missing permission row = DENIED.
def _dynamic_form_permission(user, form_key):
    try:
        from app.models import UserFormPermission
        return UserFormPermission.query.filter_by(user_id=user.id, form_key=form_key).first()
    except Exception:
        return None

def _permission_allows(perm, action):
    if not perm:
        return False
    if action == "view":
        return bool(perm.can_view or perm.can_create or perm.can_edit or perm.can_delete or perm.can_approve or getattr(perm, "can_print_export", False))
    if action == "create":
        return bool(perm.can_create)
    if action == "edit":
        return bool(perm.can_edit)
    if action == "delete":
        return bool(perm.can_delete)
    if action == "approve":
        return bool(perm.can_approve)
    if action in ["print", "export", "print_export"]:
        return bool(getattr(perm, "can_print_export", False))
    return False

def can_access_module(user, key, action="view"):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.role == "Admin":
        return True
    # Dashboard is allowed for authenticated users, but dashboard content is filtered by permissions.
    if key == "dashboard" and action == "view":
        return True
    perm = _dynamic_form_permission(user, key)
    return _permission_allows(perm, action)

def can_view_form(user, form_key):
    return can_access_module(user, form_key, "view")

def can_create_form(user, form_key):
    return can_access_module(user, form_key, "create")

def can_edit_form(user, form_key, entry=None):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.role == "Admin":
        return True
    # Edit requires explicit edit permission. No owner fallback in strict mode.
    return can_access_module(user, form_key, "edit")

def can_delete_form(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.role == "Admin":
        return True
    # Form deletion is controlled per form by before_request using the form key.
    return False

def can_upload_document(user):
    return can_access_module(user, "documents", "create")

def can_review_document(user):
    # Specific document approval is controlled by Documents approve permission.
    return can_access_module(user, "documents", "approve")

def can_create_project(user):
    return can_access_module(user, "projects", "create")

def can_manage_users(user):
    return getattr(user, "is_authenticated", False) and user.role == "Admin"


# ---------------------------------------------------------------------------
# Phase 15O - FINAL PERMISSION LOGIC
# Purpose: make Admin User Form Permissions fully control menus, pages and actions.
# Parent modules are opened automatically when any child permission is granted.
# Example: if a technician has Site Survey permission, Online Forms menu/home opens.
# ---------------------------------------------------------------------------
PARENT_CHILD_PERMISSION_KEYS = {
    "forms-home": ["site-survey", "load-assessment", "daily-site-report", "delivery-note", "testing", "commissioning", "handover"],
    "projects": ["projects", "project-workforce"],
    "project-tasks": ["project-tasks"],
    "materials": ["material-items", "material-request", "material-issue", "material-return", "material-reports"],
    "sales-crm": ["customer-inquiry", "quotation", "quotation-items"],
    "after-sales": ["service-ticket", "warranty"],
    "reports": ["project-reports", "customer-reports", "form-reports", "material-reports"],
    "customers": ["customers"],
    "employees": ["employees"],
    "teams": ["teams"],
    "notifications": ["notifications", "notification-log", "sms-queue", "whatsapp-integration", "production-readiness"],
    "ai-assistant": ["ai-assistant", "ai-reports", "ai-logs", "ai-settings"],
}

FORM_CHILD_KEYS = ["site-survey", "load-assessment", "daily-site-report", "delivery-note", "testing", "commissioning", "handover"]

def _get_perm(user, key):
    try:
        from app.models import UserFormPermission
        return UserFormPermission.query.filter_by(user_id=user.id, form_key=key).first()
    except Exception:
        return None

def _has_any_explicit_permission(user):
    try:
        from app.models import UserFormPermission
        return UserFormPermission.query.filter_by(user_id=user.id).count() > 0
    except Exception:
        return False

def _perm_has_any(perm):
    return bool(perm and (perm.can_view or perm.can_create or perm.can_edit or perm.can_delete or perm.can_approve or getattr(perm, "can_print_export", False)))

def _permission_allows(perm, action):
    if not perm:
        return False
    if action == "view":
        return _perm_has_any(perm)
    if action == "create":
        return bool(perm.can_create)
    if action == "edit":
        return bool(perm.can_edit)
    if action == "delete":
        return bool(perm.can_delete)
    if action == "approve":
        return bool(perm.can_approve)
    if action in ["print", "export", "print_export"]:
        return bool(getattr(perm, "can_print_export", False))
    return False

def can_access_module(user, key, action="view"):
    """Single source of truth for access control.

    - Admin: full access.
    - Non-admin: must have explicit permission row.
    - Dashboard: allowed after login, but its buttons/sections are filtered.
    - Parent/module keys: allowed for VIEW when any child permission exists.
    - Action buttons/routes: require the exact key/action permission.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if user.role == "Admin":
        return True
    if key == "dashboard" and action == "view":
        return True

    perm = _get_perm(user, key)
    if _permission_allows(perm, action):
        return True

    # Parent modules are only view containers. Do not allow create/edit/delete through a parent.
    if action == "view" and key in PARENT_CHILD_PERMISSION_KEYS:
        for child_key in PARENT_CHILD_PERMISSION_KEYS[key]:
            if _perm_has_any(_get_perm(user, child_key)):
                return True

    return False

def has_any_permission(user, keys, action="view"):
    return any(can_access_module(user, key, action) for key in keys)

def allowed_permission_keys(user):
    try:
        from app.models import FORM_PERMISSION_KEYS
        return [item[0] for item in FORM_PERMISSION_KEYS if can_access_module(user, item[0], "view")]
    except Exception:
        return []

def allowed_form_keys(user, action="view"):
    return [key for key in FORM_CHILD_KEYS if can_access_module(user, key, action)]

def can_view_form(user, form_key):
    return can_access_module(user, form_key, "view")

def can_create_form(user, form_key):
    return can_access_module(user, form_key, "create")

def can_edit_form(user, form_key, entry=None):
    return can_access_module(user, form_key, "edit")

def can_delete_form(user):
    # Individual form route checks the actual form key/action.
    return getattr(user, "is_authenticated", False) and user.role == "Admin"

def can_upload_document(user):
    return can_access_module(user, "documents", "create")

def can_review_document(user):
    return can_access_module(user, "documents", "approve")

def can_create_project(user):
    return can_access_module(user, "projects", "create")

def can_manage_users(user):
    return getattr(user, "is_authenticated", False) and user.role == "Admin"


# ---------------------------------------------------------------------------
# Phase 15P - Admin Full Access & Normalized Role Safety
# ---------------------------------------------------------------------------
def _is_admin_user(user):
    return str(getattr(user, "role", "") or "").strip().lower() == "admin"

# Override final access helper to avoid role spacing/case issues.
def can_access_module(user, key, action="view"):
    if not getattr(user, "is_authenticated", False):
        return False
    if _is_admin_user(user):
        return True
    if key == "dashboard" and action == "view":
        return True
    perm = _get_perm(user, key)
    if _permission_allows(perm, action):
        return True
    if action == "view" and key in PARENT_CHILD_PERMISSION_KEYS:
        for child_key in PARENT_CHILD_PERMISSION_KEYS[key]:
            if _perm_has_any(_get_perm(user, child_key)):
                return True
    return False

def can_manage_users(user):
    return getattr(user, "is_authenticated", False) and _is_admin_user(user)
