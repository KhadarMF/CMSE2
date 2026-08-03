# Phase 17B.1D – Security Login Hotfix

## Purpose
Fix the security regression introduced in 17B.1C where internal ERP pages could be opened without showing the login form.

## Fixed
- Internal ERP routes now require authentication globally, even if a route accidentally misses `@login_required`.
- Unauthenticated users are redirected to `/login` before accessing dashboard, customers, projects, reports, Customer 360, or other ERP pages.
- Public endpoints remain public only where intended:
  - `/auth/*`
  - static assets
  - health checks
  - WhatsApp webhook
  - signed public quotation links

## Expected Test
1. Open ERP in private/incognito browser.
2. Go directly to `/dashboard` → Login page must appear.
3. Go directly to `/master/customers` → Login page must appear.
4. Login with admin account → Dashboard opens.
5. Logout → Login page appears again.
6. After logout, direct `/dashboard` must not open.
