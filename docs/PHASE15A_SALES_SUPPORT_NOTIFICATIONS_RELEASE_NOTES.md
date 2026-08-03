# Phase 15A - Sales CRM, Warranty/Support, Notifications and Production Readiness

Deferred as requested:
- Full Inventory / Warehouse
- Procurement / Purchase Orders
- Formal Finance module

Added instead:
1. Sales CRM
   - Customer Inquiry
   - Follow-up status
   - Quotation with reference number and datasheet lines
2. Warranty & After-Sales Support
   - Warranty Registration
   - Service Tickets
   - Technician assignment
   - Service Visit report
3. Notifications Center
   - Create notification
   - Assign to user or all users
   - Mark as read
4. Production Readiness page
   - Database check
   - User/project/customer counts

Test:
- Copy old instance/solar_documents.db
- env\Scripts\activate
- python init_db.py
- python run.py
- Open Sales CRM, Support, System menus
