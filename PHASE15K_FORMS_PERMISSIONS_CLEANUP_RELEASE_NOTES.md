# Phase 15K – Forms Cleanup, Combined Survey & Extended Permissions

## Fixes
1. Removed duplicate Customer / Customer Name fields in CRM inquiry, warranty and service ticket forms. These are now a single customer combo field using existing customers, with typing support for a new customer.
2. Combined Site Survey and Load Assessment into one form: **Site Survey & Load Assessment Form**.
3. Expanded User Access & Form Permissions beyond the original 7 forms. It now includes projects, tasks, issues, materials, reports, CRM, quotations, service tickets, warranty, notifications, AI, production readiness and admin pages.
4. Added Print / Export permission option.
5. Added database migration for new combined survey fields and permission export column.

## Test
- Run `python init_db.py`
- Open Forms & Reports → Site Survey & Load Assessment
- Open Admin → User Form Permissions
- Open Sales CRM / Support forms and confirm only one customer field is visible.
