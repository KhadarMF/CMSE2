# Phase 15M - User Permissions Full Rework

This phase fixes User Form Permissions so they work as a real ERP access-control system.

## Main fixes
- Strict permission mode for all non-admin users.
- Missing permission row now means DENIED, not role fallback.
- Menu items are hidden unless the user has permission.
- Direct URL access is blocked unless the user has permission.
- User Form Permissions page is reorganized with grouped modules.
- Quick permission presets added: Technician Forms Only, Support User, Sales User, Manager View.
- Notification bell hidden if user has no Notification permission.
- Dashboard quick access buttons filtered by permissions.

## Important test
1. Login as Admin.
2. Go to Admin > User Form Permissions.
3. Select Khalid Ibrahim.
4. Click Technician Forms Only.
5. Save.
6. Logout from Khalid and login again.
7. Khalid should only see Forms-related menu and the allowed forms.
8. Test direct URL /sales, /materials, /ai, /support: access should be denied unless allowed.
