# Phase 17B.2C - Security Session Reset Fix

This hotfix fixes the login/session issue found after 17B.2.

Changes:
- Forces a new hard-coded session cookie name: `cmse_erp_session_v17b2c`.
- Does not allow Render `SESSION_COOKIE_NAME` env var to keep old unsafe cookies alive.
- Adds session security version check: `17b2c`.
- Clears old/stale sessions and redirects to login.
- Makes Flask-Login user loader safe against invalid cookies.
- Keeps 17B.2 permissions unification code intact.

Test:
1. Deploy.
2. Open Incognito.
3. Go to `/dashboard` -> Login required.
4. Login -> Dashboard opens.
5. Logout -> session clears.
6. Go to `/dashboard` again -> Login required.
