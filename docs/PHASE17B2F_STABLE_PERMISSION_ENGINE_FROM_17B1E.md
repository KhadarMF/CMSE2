# Phase 17B.2F - Stable Permission Engine from 17B.1E

Built from the confirmed stable 17B.1E security session hardening baseline.

## What changed
- Removed self-referencing parent-child permission entries.
- Added guard logic so parent menu permissions never recurse into themselves.
- Kept the 17B.1E authentication/session hardening unchanged.
- Did not touch login, logout, session cookie name, database, Customer 360, WhatsApp, or AI.

## Purpose
This build is intended to restore a stable baseline while keeping the permission engine safe from RecursionError and 500 login failures.

## Test checklist
1. Open Incognito/Private window.
2. Go to /dashboard: it must show Login.
3. Login as Admin: Dashboard must open.
4. Logout: session must clear and return to Login.
5. Login as another user: access must follow that user permissions.
6. Admin > System > Form Permissions should open.
7. No RecursionError should appear in Render logs.
