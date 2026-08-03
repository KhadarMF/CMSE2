# Phase 15D - Advanced Service Ticket & Customer Complaint Workflow

This phase improves After-Sales & Warranty support for Cadceed-Maal Solar Energy.

## Added / Improved
- Advanced Service Ticket / Customer Complaint form
- Complaint source dropdown: WhatsApp, Phone, Office, Branch, Website, etc.
- Ticket category dropdown: Inverter Fault, Battery Issue, Pump Problem, Wiring Problem, Monitoring Issue, etc.
- Priority and SLA-style due date handling
- Assigned Technician from Employees table
- Supervisor / Responsible User from Users table
- Ticket workflow: Open, Assigned, In Progress, Waiting Parts, Resolved, Closed, Not Warranty
- Service Visit Report with fault found, root cause, work done, parts used, test result and customer feedback
- Root Cause / Corrective Action / Preventive Action section
- Customer Confirmation field
- Ticket Report, Print and PDF buttons
- Support dashboard counters: open, urgent, waiting parts, overdue
- Filtering tickets by status, priority and category

## Migration
Run:
python init_db.py

This adds new support_ticket and service_visit columns to existing databases without deleting old data.
