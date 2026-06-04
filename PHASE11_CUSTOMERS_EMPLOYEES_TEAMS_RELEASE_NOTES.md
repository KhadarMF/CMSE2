# Phase 11 - Customers, Employees, Teams and Workforce Reports

Added:
- Customer master table
- Employee master table
- Teams module with team leader and members
- Project workforce assignment: assign teams and direct employees to projects
- Full Project Report now includes workforce/teams/employees
- Customer table sync from existing project customer names during `python init_db.py`

Important:
- This phase adds new database tables only.
- Existing projects, forms, documents, tasks and issues remain unchanged.
- Existing Project.customer_name remains supported to avoid breaking old data.

Local testing:
1. env\Scripts\activate
2. pip install -r requirements.txt
3. python init_db.py
4. python run.py
5. Open Master Data → Customers / Employees / Teams
6. Open a Project → Manage Workforce
7. Open Reports → Full Project Report