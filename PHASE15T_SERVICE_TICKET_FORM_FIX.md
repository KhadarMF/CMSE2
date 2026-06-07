# Phase 15T — Service Ticket Form Fixes

This release corrects the New/Update Service Ticket workflow reported during testing.

## Fixed

1. Customer field changed from textbox/datalist to a real combo box reading from the `Customer` table.
2. Added optional `New Customer Name` field for walk-in/new customers not yet registered.
3. Customer phone and location auto-fill from the selected customer when available.
4. Warranty section improved:
   - Warranty registration select still reads from `WarrantyRegistration` table.
   - Added `Warranty / Claim Notes` input for warranty details, invoice/serial/reference notes.
   - Added quick link to create a Warranty Registration if it is not listed.
5. Assigned To / Technician field improved:
   - Reads from `Employee` table.
   - Shows employee name, job title and status.
   - No longer filters out employees only by status, so employees are visible even if status text differs.
6. Update Ticket form improved:
   - Added Assigned To / Technician selector from Employee table.
   - Added Supervisor / Responsible User selector.
   - Added Warranty / Claim Notes field.
   - Added Select / Jump to Ticket dropdown to choose another service ticket.
7. Added `warranty_note` field to `SupportTicket` with safe auto-migration for existing databases.

## Files changed

- `app/models.py`
- `app/routes/support_routes.py`
- `app/templates/support/ticket_form.html`
- `app/templates/support/ticket_detail.html`
- `app/templates/support/ticket_report.html`
