# Phase 17B.1E – Security Session Hardening

This hotfix fixes the critical login bypass/session issue.

## Changes
- Changed Flask session cookie name to `cmse_erp_session_v17b1e` to invalidate unsafe cookies from previous hotfix builds.
- Added a strict global authentication gate for all internal ERP routes.
- Public routes are limited to login, health check, WhatsApp webhook, and signed quotation public links.
- Logout now clears the full session.
- Login uses fresh non-remembered sessions.
- Protected routes redirect to `/login` when user is not authenticated.

## Required Test
1. Open Incognito / Private browser.
2. Visit `/dashboard` → must redirect to login.
3. Login with valid admin credentials → dashboard opens.
4. Logout → login page opens.
5. After logout visit `/master/customers` → must redirect to login.
6. Close normal browser tabs and reopen `/dashboard`; old unsafe sessions should no longer work because cookie name changed.
