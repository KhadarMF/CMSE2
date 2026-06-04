# Phase 13 - Project-Based Payroll with Bulk / Batch Entry

Fixes Phase 12 payroll concept.

- Payroll is per project, not monthly salary.
- A person can work on many projects in one month.
- Bulk / Batch Entry form: select one project, work date, and all employees who worked.
- Finance can record partial/full payments for each employee line.
- Employee statement shows projects worked, total due, paid and balance.
- Project payroll report shows employees, due, paid and remaining balance.

Important: copy old `instance/solar_documents.db` into this phase before testing, then run `python init_db.py`.
