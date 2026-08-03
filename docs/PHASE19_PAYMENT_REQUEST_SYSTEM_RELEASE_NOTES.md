# Phase 19 – Payment Request System

## Scope
Request → Manager Approval → Finance Approval → Payment, general purpose with optional links to a Project and/or a Material Request. Payment methods: Zaad, E-Dahab, Bank Transfer, Cash, Cheque, Other. Currencies: USD, SLSH.

This mirrors the existing Project Payroll module's two-tier approval pattern (`MANAGER_ROLES` / `FINANCE_ROLES` in `app/routes/payroll_routes.py`) on purpose — same roles, same "Approved → Partially Paid → Paid" progression, same payment-methods list (`PROJECT_PAYMENT_METHODS`, reused directly as `PAYMENT_REQUEST_METHODS` so reporting stays consistent across both modules).

## Added
- **Models** (`app/models.py`): `PaymentRequest`, `PaymentRequestPayment`, plus `PAYMENT_REQUEST_STATUSES`, `PAYMENT_REQUEST_CATEGORIES`, `PAYMENT_REQUEST_METHODS`, `PAYMENT_REQUEST_CURRENCIES`. A request supports partial payments (multiple `PaymentRequestPayment` rows against one request, same pattern as `ProjectPayrollEntry`/`ProjectPayrollPayment`), with `total_paid` / `balance` computed properties.
- **Routes** (`app/routes/payment_routes.py`, blueprint `payments`, prefix `/payments`):
  - `/` dashboard, `/requests` (filterable list), `/requests/my`, `/requests/create`, `/requests/<id>` (detail)
  - `/requests/<id>/approve-manager`, `/requests/<id>/approve-finance` — role-gated (`MANAGER_ROLES`, `FINANCE_ROLES`, same lists as payroll)
  - `/requests/<id>/reject` (POST, requires a reason, gated to whichever stage is active)
  - `/requests/<id>/cancel` (POST, requester or Admin only, only while still at first stage)
  - `/requests/<id>/payment` (POST, Finance-tier only, blocks overpayment past the remaining balance)
  - `/requests/<id>/attachment`, `/requests/<id>/payments/<id>/proof` — file downloads
  - `/reports` — totals by category and by payment method
- **Templates** (`app/templates/payments/`): `dashboard.html`, `requests.html`, `my_requests.html`, `request_form.html`, `request_detail.html`, `reports.html`.
- **Permissions**: new key `payment-requests` registered in `FORM_PERMISSION_KEYS` (models.py, category "Finance") and mapped in `permission_enforcer.py` (`ENDPOINT_KEYS` + `BLUEPRINT_FALLBACK_KEYS`). Same strict-explicit-grant model as every other module: Admin has full access automatically; every other role needs an explicit `UserFormPermission` row via Admin → Form Permissions before they can use this at all. **Nothing is granted to any non-Admin role by default** — see "Before this is usable" below.
- **Notifications**: uses the existing `app.notifications.notify_roles` / `notify_user` helpers — Manager roles are notified on submission, Finance roles on manager-approval, the requester on each status change. Silently no-ops if SMTP isn't configured (same as everywhere else this helper is used); doesn't block the request flow either way.
- **Nav**: new "Finance" section in `base.html`, gated by `can_access_module(current_user, 'payment-requests')`.
- **File uploads**: reuses `document_routes.py`'s save pattern (`secure_filename` + timestamp prefix into `UPLOAD_FOLDER`), but with microsecond precision instead of second precision — see the note under "Related, worth knowing" below.

## Design decisions worth knowing about
- **Approval is role-based, not org-chart-based.** There's no `Department.head_user_id` in this schema, so "Department Head" approval is implemented the same way payroll already does it: anyone with role Admin, Management, or Operation Manager can give first-level approval on *any* request, not just their own department's. If you want approval scoped to an actual manager-of-that-department relationship, that's a real schema change (adding a head/manager field to `Department`), not a small tweak — flag it if you want it.
- **Request numbering uses the row's own auto-increment ID** (`PR-YYYYMMDD-00042`), not a timestamp. This was a deliberate choice after finding and fixing a real timestamp-collision bug in the backup system (Phase 18A.4) — same risk existed here in theory, so it's built collision-proof from the start rather than retrofitted later.
- **A request can only be self-cancelled by the requester while still "Pending Manager Approval."** Once a manager has touched it, only Manager/Finance can reject it (with a reason), on the theory that silent cancellation after someone already spent time on approval is worse than a rejection with an audit trail.
- **File restore in the uploads folder is a merge, not a mirror** (inherited limitation from Phase 18A.4 — same caveat applies to payment attachments and payment proofs as everything else in `UPLOAD_FOLDER`).

## Before this is usable
1. **Grant permissions.** Go to Admin → Form Permissions and give the "Payment Requests" key `can_view` + `can_create` to whoever should be able to submit requests, `can_approve` to Managers and Finance Officers, and `can_print_export` to anyone who needs to download attachments or payment proof — that's a separate action from `can_view` in this app's permission model (same as document downloads elsewhere), easy to forget and then wonder why a download link 403s.
2. **No migration step needed.** Like payroll and materials, this blueprint has a `before_app_request` hook that calls `db.create_all()`, so the two new tables get created automatically on first request after deploy.
3. **Consider a backup before first use in production**, same as any schema change — cheap insurance, and Restore is right there if needed.

## Not built (said explicitly, not just implied)
- No live API integration with Zaad or eDahab. Recording a payment means typing in the transaction reference and optionally attaching a screenshot — it does not call out to Telesom/Somtel to move money or verify the reference is real. Real API access to either provider requires a business agreement with the telco; if you have that, this would need a follow-up phase to actually integrate it, and this module would need to change from "record what happened" to "trigger and confirm what happens."
- No multi-line payment requests (one request = one payee/purpose/amount). If you regularly need one request covering several line items to different payees, that's a bigger schema change (a `PaymentRequestLine` table) and worth its own phase rather than bolting on.
- No department-head-specific routing (see above).
- No budget/spending-limit checks against a department or project budget — approval is purely procedural (did a Manager and Finance person click approve), not tied to whether the money is actually available.

## Testing
Automated (not part of the shipped code — delete after running): full lifecycle (create → manager approve → finance approve → partial payment → final payment → Paid), reject at each stage, cancel, overpayment rejection, file upload/download for both attachments and payment proof, permission denial for ungranted users and correct denial message per role, nav link gating, Admin bypass, and — because it touches the same `db.metadata.sorted_tables` machinery — a combined test confirming Phase 18A.4's restore engine correctly wipes and reloads the two new tables with zero additional code.

One real bug was caught and fixed during this testing: recording a payment computed the new status (Partially Paid / Paid) against a stale in-memory copy of the request's payment list, because an earlier balance check in the same request had already cached that collection before the new payment was added. Every payment recorded would have silently left the request stuck at "Approved" regardless of how much was actually paid. Fixed by appending to the ORM relationship instead of only setting the foreign key, which keeps the in-memory collection consistent — confirmed with a test that checks the status transition explicitly, not just that the payment row got created.

## Not changed
Backup/Restore (Phase 18A.4), Payroll, Materials, all other existing modules. `models.py` changes are purely additive (new classes and constants appended at the end, one new tuple inserted into `FORM_PERMISSION_KEYS`) — nothing existing was modified.
