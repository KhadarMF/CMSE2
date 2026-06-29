# Phase 17B.2 – Permissions Unification

## Purpose
This release unifies Role Permissions, User/Form Permissions, menu visibility, and route protection so they all use one permission engine.

## Added
- Unified permission engine in `app/permissions.py`.
- Role permission templates in `app/role_permissions.py`.
- Role → User/Form Permissions sync button.
- Permission Inspector page for Admin.
- Role overview now shows template-based access summary.
- Menu create links now respect Create permission, not just View permission.
- WhatsApp Conversation Center endpoints mapped into permission enforcement.
- Customer 360 endpoint mapped to Customers permission.

## Access Logic
- Admin: full access automatically, no manual rows needed.
- Non-admin with User/Form Permission rows: those rows are the final access control.
- Non-admin with no rows: role template fallback is used.
- Menu visibility and direct URL access use the same `can_access_module()` engine.

## Admin Test Checklist
1. Login as Admin.
2. Go to System → Form Permissions.
3. Select a non-admin user.
4. Click `Sync Role → Permissions`.
5. Logout/login as that user.
6. Confirm menu only shows allowed modules.
7. Try direct URL to denied module; it should redirect/deny.
8. Use System → Permission Inspector to verify effective permissions.

## Security Note
This release is based on 17B.1E Security Session Hardening. Login/session authentication was not weakened.
