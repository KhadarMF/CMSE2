# Phase 17B.1C – Login Workspace Hotfix

## Fixed
- Prevented `/auth/login` from rendering inside the authenticated ERP shell.
- Root `/` now redirects authenticated users to Dashboard instead of Login.
- Removed saved `/auth/*` entries from workspace tabs, recent pages, favorites, and closed tabs.
- Customer 360 Workspace remains available through Master Data → Customers → customer name / Open Workspace.

## Test
1. Login as Admin.
2. Open Dashboard, Customers, and Customer 360 Workspace.
3. Confirm login form does not appear inside the ERP workspace.
4. Confirm Windows tabs still work.
