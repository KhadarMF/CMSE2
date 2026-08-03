# Phase 20F — Employee Workspace 360

## What changed

- Added a dedicated Employee Workspace 360 page for every employee.
- Added employee summary KPIs for projects, teams, tasks, payroll, and service work.
- Added Overview, Projects, Teams, Tasks, Payroll, Service, and Timeline tabs.
- Added direct links to employee task reports, payroll statements, profile editing,
  assigned projects, payroll entries, service tickets, and team records.
- Employee names in the employee list now open Workspace 360.
- Creating or editing an employee now returns to that employee's Workspace 360.
- Added a permission-aware Delete action to the employee form, list workflow,
  and Workspace 360.

## Safe employee deletion

Permanent deletion is allowed only when an employee has no linked operational
history. The application checks team leadership, team memberships, project
assignments, project tasks, both payroll systems, service tickets, and service
visits before deleting.

If linked history exists, deletion is blocked and the user is shown the exact
records that must be preserved. Set the employee status to `Inactive` instead.
This protects payroll, project, task, team, and service audit history.

## Permissions and security

- Employee Workspace 360 follows the existing `employees` view permission.
- The Delete action requires the existing `employees` delete permission.
- All delete requests use POST and include CSRF protection.
- Buttons and tabs are hidden when the signed-in user lacks the related module
  permission.

## Deployment

No database schema migration is required. Replace the application files, keep
the existing `.env` and database, install requirements if needed, then restart
the application.

## Verification

- Full automated suite: `30 passed, 1 skipped`.
- Desktop and 390 x 844 responsive browser checks passed.
- Employee history tabs, safe-delete modal, navigation, and linked operational
  records were verified with realistic demo data.
- Browser console errors: none.
