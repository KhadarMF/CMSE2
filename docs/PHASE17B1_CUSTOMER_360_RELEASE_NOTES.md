# Phase 17B.1 - Customer 360 Workspace

Built on Phase 17A.3B Smart Workspace.

## Added
- Customer 360° Workspace page.
- New route: `/master/customers/<customer_id>`.
- Customers list now opens Customer 360 from the customer name and a new `360°` action button.
- Customer summary cards:
  - Quotations
  - Total quotation value
  - Projects
  - Service tickets
- Customer workspace tabs:
  - Overview
  - Quotations
  - Projects
  - Inquiries
  - WhatsApp
  - Service
  - Documents
  - Timeline
- Aggregates related records by customer name, customer id, and phone suffix where available.
- Timeline combines quotations, projects, inquiries, service tickets, and WhatsApp activity.

## Not changed
- No database schema changes.
- No authentication changes.
- No permission logic changes.
- Existing customer edit form remains available.

## Test Checklist
1. Login as Admin.
2. Open Master Data > Customers.
3. Click a customer name or `360°`.
4. Check that Overview opens.
5. Check each tab: Quotations, Projects, Inquiries, WhatsApp, Service, Documents, Timeline.
6. Open linked quotation/project/ticket records.
7. Confirm tabs/window manager from 17A.3B still works.
