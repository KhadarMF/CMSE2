# Phase 20H — Team Leader Payment Requests and Daily Reporting

## What is included

- A Team Leader can create and track their own Payment Requests.
- The request records Team, assigned Project, request type, payee, amount,
  purpose, needed date, and optional attachment.
- A Team Leader can create a Team Daily Report for an assigned project.
- The report records attendance, hours, planned/completed work, quantity,
  materials, equipment, delays, issues, safety, next-day plan, and progress.
- Only one report is allowed for the same Team + Project + Date.
- Submitted daily reports are locked until Management returns them as
  `Need Correction` or `Rejected`.
- Only approved daily reports affect Project Command Center physical progress.

## Access and approval rules

Team Leader identity is established by linking these records:

1. User account → Employee (`Employee.user_id`)
2. Employee → active Team (`Team.leader_employee_id`)
3. Team → Project Workforce (`ProjectTeamAssignment` with status `Active`)

A Team Leader sees only teams they lead and projects assigned to those teams.
Payment Request detail is restricted to the requester, Management, and Finance.
The requester cannot approve their own payment request or daily report.

Payment workflow:

```text
Team Leader submits → Manager approval → Finance approval → Payment recorded
```

Daily Report workflow:

```text
Draft → Submitted → Approved / Need Correction / Rejected
```

## Database migration

Revision `b20h0000a001` adds the Team Leader fields and the daily-report unique
constraint without deleting existing data. Revision `b20h0000a002` repairs
legacy installations that were missing the `payment_request` and
`payment_request_payment` tables even though their Alembic baseline had
already been stamped. The repair is additive and preserves existing tables.

Before upgrading, download a fresh backup. Then run:

```powershell
python -m flask db upgrade
```

On Render, keep the permanent **Pre-Deploy Command** as:

```text
flask db upgrade
```

Do not run `init_db.py` against an existing database.

For a newly extracted local copy, simply run `python run.py`. The local
launcher creates the git-ignored `.env`, generates a unique `SECRET_KEY`, and
applies migrations. For a recognized full legacy SQLite database without an
Alembic stamp, it first creates a timestamped copy in `backups/`, stamps the
documented baseline, and upgrades through Phase 20H. It never overwrites an
existing valid secret, and this convenience is disabled on Render/production.

After deployment, the log should include:

```text
Running upgrade b20g0000a001 -> b20h0000a001
Running upgrade b20h0000a001 -> b20h0000a002
```

## Administrator setup

1. Create or edit the user's account and choose role `Team Leader`.
2. Open Employees and link that employee to the user account.
3. Open Teams and select the employee as Team Leader; keep the Team Active.
4. Open Project Workforce and assign that Team to each permitted Project with
   status `Active`.
5. The user can then open **Finance → New Payment Request** and
   **Projects → New Daily Report**.

## Verification

- Existing and new automated suite: 34 passed, 1 intentionally skipped.
- Missing-payment-table repair regression test: passed.
- Fresh SQLite migration through revision `b20h0000a002`: passed.
- Unauthorized project, team, and payment-record access tests: passed.
