# Phase 15P - Admin Permissions Display Fix

Fixes:
- Admin users now show as FULL ACCESS in User Form Permissions.
- Admin matrix appears checked and disabled to avoid confusion.
- Admin permission rows are not required and are not saved as blank rows.
- Non-admin permission saving now stores only ticked permission rows.
- Admin role comparison normalized to avoid case/space issues.

Test:
1. Admin > User Form Permissions.
2. Select Admin: all boxes should be checked/disabled and marked Admin Full Access.
3. Select Khalid or technician user: choose Technician Forms Only, Save.
4. Logout/Login as Khalid. He should see Dashboard + Online Forms only.
