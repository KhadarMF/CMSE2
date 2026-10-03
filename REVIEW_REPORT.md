# Solar ERP review and repairs

Reviewed 12 September 2026. Source: `solar_doc_phase20K_survey_split.zip`.
The original ZIP and source directory were not changed. All execution used an
extracted workspace copy and disposable databases.

## Result

The corrected build fixes reproduced migration, survey, approval, permission,
payment, and setup defects. The full regression suite completed with **65 passed,
1 skipped**. The skipped test requires a dedicated PostgreSQL database.
The native Windows PDF renderer failed during testing; exports now run in an
isolated process and provide a printable HTML fallback instead of taking down
the ERP. Direct PDF rendering still needs a working WeasyPrint/native runtime.

## Changes made

| Area | Problem found | Repair |
| --- | --- | --- |
| Migrations | Replaying the survey upgrade failed with duplicate columns; the legacy repair test expected an obsolete head. | Detect existing survey columns/table, preserve their contents, and check the current migration head. |
| Pumping survey | Missing permission catalog entry and incomplete project, milestone, dashboard, and report integration. | Make the survey assignable and include it in the relevant project commands, evidence requirements and totals. |
| Readiness | Legacy load assessment was still counted as another required form after combining it with the off-grid survey. | Use the relevant survey plus the five other current forms; retain legacy records in historical reports. |
| Existing pumping projects | Default survey requirements still pointed to the off-grid form. | New migration `b20k0000a002` updates only unlinked default requirements on unfinished pumping milestones. Custom links and completed historical milestones are preserved. |
| Form approvals | Create requests could forge Approved status; editing approved content retained approval. | Accept Draft/Submitted on creation, reset edited forms to Draft, clear reviewer metadata, and record the transition. Reopen affected milestone approvals when their supporting evidence changes. |
| Historical surveys | Renamed forms could hide old approval history and measurements omitted from the new editor. | Include historical module names in history lookup and show retained legacy measurements in detail/print/export views. |
| Duplicate forms | Editing could move a singleton form onto a project that already had one. Parallel creates could race. | Validate projects, check duplicates on edit, and serialize duplicate checks and saves. Daily reports retain team/project/date uniqueness. |
| Documents | Upload requests could forge approval; identical filenames uploaded in the same second could overwrite files. | Validate initial status/project, use unique storage names, clear stale reviewer metadata on new versions, and prevent reviewing one's own uploaded version. |
| Permissions | View-only users could reach some modifying actions; form PDF access used a broad reporting permission; project editing incorrectly also required create permission. | Use explicit mutation/approval permissions, the specific form's export permission, and the project's edit permission. Honor per-form delete permissions. |
| CSRF | Ten toggle/remove/approval/notification operations changed state through GET links. | Convert routes and their buttons to POST with CSRF tokens. Match workforce removal records to the requested team/project. |
| Payment requests | Invalid/nonfinite values and fractional cents could defeat validation; a one-cent debt could be marked paid, and overpayments of one cent were allowed. | Round valid input before comparing balances, reject invalid/oversized values, retain the final cent, and serialize payment recording. |
| Payroll | Payments could be recorded without approval or above the balance; payment status could use stale relationship data. | Enforce approval and remaining balance on the server, serialize writes, and update status from the appended payment. New batches start as Draft/Submitted. |
| Numeric storage | Nonfinite numeric values could reach database binding; numeric subclasses lacked SQLAlchemy cache declarations. | Reject invalid/nonfinite values and declare safe type caching. |
| Login/configuration | Invalid user IDs could raise errors; `.env` overrode process database/security configuration. | Reject malformed/inactive sessions and give process configuration precedence. |
| First run | The launcher could leave a new database without an administrator; initialization used schema creation instead of migrations and a shared default password. | Use Alembic, seed missing reference data, create a unique bootstrap password, preserve existing administrators, and stop on unrecognized legacy schemas. Local debug is off by default. |
| PDF availability | WeasyPrint's native Windows text renderer crashed during a real export. | Render in a bounded child process for reports, quotations, and tickets. On failure/timeout show the complete printable report with Print / Save as PDF. |

## Verification

- Original suite: 42 passed, 1 failed, 1 skipped. The failure reproduced the survey migration replay problem.
- Expanded suite: 65 passed, 1 skipped. The retained tests cover existing dashboard,
  project, team-leader, employee, security, money, and migration behavior.
- Added regressions cover survey permissions and persistence, historical data,
  approvals, duplicate edits, nonfinite amounts, final-cent settlement, payroll
  approvals, session handling, permission boundaries, CSRF, bootstrap behavior,
  environment precedence, evidence reopening, and PDF failure handling.
- Two concurrent payment submissions cannot both spend the same remaining balance;
  two concurrent singleton form submissions produce one record.
- Common authenticated pages render successfully, including project details,
  both survey editors, documents, permissions, accounting, payroll, materials,
  payments, and full project reports.
- An isolated real `python run.py` startup returned a healthy database, accepted
  the first-run administrator login with CSRF, and served the pumping survey page.
- Python compilation passed. Native PDF export was attempted and its failure
  was reproduced. Printable fallback and continued dashboard availability were checked.

Two existing test expectations were intentionally updated: the migration head now
comes from Alembic, and readiness reflects six current forms rather than seven.
The legacy load assessment remains available but no longer reduces readiness.

## Applying the build

Use the included `README.md`. Preserve your database, uploads and `.env`; install
the requirements and run `python -m flask --app wsgi db upgrade` for an existing
Alembic-managed installation. The new head is `b20k0000a002`. Administrators must
explicitly grant the new pumping survey permissions to relevant staff.

## Limits and remaining verification

No live database or deployment credentials were supplied, so production data
migration and PostgreSQL behavior were not exercised. Email, WhatsApp, AI API
calls, and live backup restoration were not run. This is a source review and
regression repair, not certification of every ERP business rule or of financial
reporting across currencies. Legacy financial data, exchange-rate treatment, and
payroll carry-forward policy still require validation against the business's records.

Direct PDF download remains dependent on the host's native WeasyPrint libraries.
The tested Windows runtime raised a native access violation and the isolated
renderer could not complete. Browser Print / Save as PDF is the available fallback
on this host. No system libraries were replaced.

The repository still emits SQLAlchemy/Alembic deprecation warnings; they do not
fail the tests. Generated credentials, databases, logs containing setup credentials,
uploads, caches, and compiled bytecode are excluded from the delivery ZIP.
