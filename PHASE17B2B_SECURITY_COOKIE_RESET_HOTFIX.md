# Phase 17B.2B - Security Cookie Reset Hotfix

## Purpose
This hotfix keeps the working Phase 17B.2 Permissions Unification code, but changes the Flask session cookie name to force all browsers to login again after deployment.

## Fixes
- Invalidates old browser session cookies from previous builds.
- Prevents old authenticated sessions from entering the ERP immediately after deploy.
- Keeps 17B.2 permissions unification intact.
- Does not add the stricter cmse_logged_in flag that caused a 500 error in 17B.2A.

## Test
1. Deploy this ZIP.
2. Open Incognito/Private browser.
3. Visit /dashboard: must redirect to /login.
4. Login with valid admin credentials.
5. Dashboard should open.
6. Logout and revisit /dashboard: must redirect to /login.
