# Phase 17B.2A - Security Re-Lock Hotfix

This hotfix fixes the login bypass reported after Phase 17B.2.

## Changes
- New session cookie name: `cmse_erp_session_v17b2a` to invalidate old unsafe cookies.
- Internal ERP pages require both Flask-Login authentication and a fresh `cmse_logged_in` session flag.
- Old sessions/cookies from previous unsafe builds are cleared.
- `/auth/login` redirects to Dashboard only when the current safe session flag exists.
- Logout clears the whole session.

## Test
1. Open Incognito/Private browser.
2. Visit `/dashboard` directly. It must redirect to `/login`.
3. Login with correct admin credentials. Dashboard must open.
4. Logout.
5. Visit `/dashboard` again. It must redirect to `/login`.
