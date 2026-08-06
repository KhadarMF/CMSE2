# Solar Project Document & Approval Management System — Phase 8

## Phase 20E — Project Command Center

Open any project to see a unified Command Center with overall progress,
milestones, a task Gantt timeline, physical and financial progress, procurement,
document readiness, issues and risks, and an AI/rule-based project forecast.
See `PHASE20E_PROJECT_COMMAND_CENTER_RELEASE_NOTES.md` for calculation and access
control details. This phase uses existing records and requires no schema change.

## Phase 20F — Employee Workspace 360

Employees now have a unified Workspace 360 with profile details, project and
team assignments, task progress, payroll balances, service history, and an
activity timeline. A safe Delete action removes only unused employee records;
employees with linked operational history must be set to Inactive so financial
and project records remain intact. See
`PHASE20F_EMPLOYEE_WORKSPACE_360_RELEASE_NOTES.md`. No schema migration is
required.

## Phase 20H — Team Leader Self-Service

Team Leaders linked through Employee → Team can now submit their own Payment
Requests and create one Team Daily Report per assigned project, team, and day.
They only see teams they lead, projects assigned to those teams, and their own
payment requests. Manager and Finance approvals remain separate. Deploy this
phase with `flask db upgrade`; do not run `init_db.py` on an existing database.
See `PHASE20H_TEAM_LEADER_SELF_SERVICE_RELEASE_NOTES.md`.

## Phase 20I — Evidence-Based Milestone Engine

Every project now receives six weighted delivery milestones: Survey, Design,
Procurement, Installation, Testing/Commissioning, and Handover. Physical,
procurement, and document progress are calculated from linked operational
records. A 0% dimension is displayed as N/A and is excluded from the score.
Team Leaders can submit a ready milestone, but a different manager must approve
it. The system blocks completion when required evidence or critical work is
missing; emergency completion needs an audited reason. See
`PHASE20I_MILESTONE_ENGINE_RELEASE_NOTES.md`.

## Earlier Phase 8 notes

Phase 8 focuses on preparing the system for real deployment and multi-user use.

## Added in Phase 8

- PostgreSQL support using `DATABASE_URL`
- `.env` support using `python-dotenv`
- Production configuration
- `wsgi.py` for deployment
- `serve_waitress.py` for Windows production-style serving
- Health check endpoint: `/health`
- Upload folder environment setting
- Max upload size environment setting
- Deployment guides:
  - Render
  - Contabo Windows VPS
  - LAN testing
- SQLite export to JSON script
- Database table creation script
- Improved `.gitignore`

## Run locally

```bash
cd solar_doc_approval_phase8
python -m venv env
env\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python init_db.py
python run.py
```

Open:

```text
http://127.0.0.1:5000
```

For LAN testing:

```text
http://YOUR-IP:5000
```

Example:

```text
http://10.10.10.62:5000
```

## Production-style local run on Windows

```bash
env\Scripts\activate
python serve_waitress.py
```

## PostgreSQL setup

Set in `.env`:

```text
DATABASE_URL=postgresql://username:password@localhost:5432/solar_doc_system
```

Then run:

```bash
python init_db.py
```

## Health check

Open:

```text
http://127.0.0.1:5000/health
```

Expected:

```json
{"status":"ok","database":"ok"}
```

## Export SQLite data to JSON

```bash
python export_sqlite_to_json.py
```

Output:

```text
exports/solar_doc_export.json
```

## Deployment docs

Read:

- `deployment_lan_testing.md`
- `deployment_contabo_windows.md`
- `deployment_render.md`

## Default admin

```text
Email: admin@cadceedmaal.com
Password: Admin@12345
```

Change the password before real use.

## Phase 9 Additions

Phase 9 adds a stronger operations layer for project execution:

- Project Task Management
- Issue & Risk Tracker
- Enhanced Dashboard with task and issue counters
- Project Detail summaries for tasks and issues
- My Tasks page now includes assigned project tasks and assigned issues

After deploying Phase 9 to Render, run:

```bash
python init_db.py
```

This creates the new `project_task` and `project_issue` tables without deleting existing data.

Recommended Render environment variable:

```text
PYTHON_VERSION=3.10.5
```


## Phase 10 Reports Upgrade
- Full Project Report
- Customer Report by customer name
- PDF export for project and customer reports
- No new database tables required.


## Phase 11 Customers / Employees / Teams
- Customer master table
- Employee master table
- Teams with leader and members
- Project workforce assignment
- Full Project Report includes workforce and teams


## Phase 12 Project Payroll
- Monthly employee project salary/wage entries
- Previous balance and remaining balance
- Finance payment recording
- Employee and project payroll statements
- Full Project Report includes payroll summary


## Phase 13 Project-Based Payroll
- Payroll per project, not monthly salary.
- Bulk/batch data entry for all employees who worked on one project/date.
- Finance payment tracking and employee/project statements.


## Phase 13A Menu and Reports Fix
- Compact grouped menu.
- Project report payroll query fixed.
- Customer reports include payroll balance.


## Phase 14A Materials
- Material Request datasheet with item and description
- Ref numbers for requests/issues/returns
- Project material report and returns report


## Phase 15E
Notification Center, Notification Log, Email Notifications, SMS Queue without API, WhatsApp future settings, Sales CRM, and user-specific form permissions have been added.
