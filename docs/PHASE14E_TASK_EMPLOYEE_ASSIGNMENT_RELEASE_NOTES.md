# Phase 14E - Task Assignment to Employees

Fix requested:
- Project Task "Assigned To" should come from Employees table, not app Users table.

Changes:
1. Task form now has:
   - Assigned Employee: from Employees table
   - Responsible User / Supervisor: from Users table
2. Existing old user-based task assignments are preserved for compatibility.
3. Task list now shows:
   - Assigned Employee
   - Supervisor
4. Task filters now include employee filtering.
5. Employee Task Report added:
   - total tasks
   - completed tasks
   - open tasks
   - overdue tasks
6. Employee list includes Task Report shortcut.
7. Database migration added for existing databases:
   - assigned_employee_id
   - supervisor_user_id

Local testing:
- Copy old instance/solar_documents.db into this folder
- env\Scripts\activate
- python init_db.py
- python run.py
- Open Projects → Project Tasks → New Task
