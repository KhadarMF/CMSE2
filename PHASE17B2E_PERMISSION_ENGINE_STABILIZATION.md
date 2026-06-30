# Phase 17B.2E - Permission Engine Stabilization

## Fixed
- Resolved Render 500 error caused by `RecursionError: maximum recursion depth exceeded`.
- Stabilized `app/permissions.py` role permission lookup.
- Added cycle/self-reference protection for parent-child permission keys.
- Kept login, session, database, Customer 360, WhatsApp, and UI unchanged.

## Root Cause
`_role_allows()` recursively checked parent-child permissions. Some parent keys included themselves or cyclic child references, causing infinite recursion.

## Test
1. Deploy.
2. Open Incognito.
3. `/dashboard` should require login.
4. Login as Admin.
5. Logout.
6. Login as another user.
7. Admin login should still work afterwards.
