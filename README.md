# Solar ERP — reviewed Phase 20K with refreshed interface

**Notifications fix — 14 September 2026:** this release includes private recipient
inboxes, live unread counts, workflow/form alerts, and email delivery after commit.
Run `python -m flask --app wsgi db upgrade` before restarting an existing deployment.
The new migration is `b20k0000a003`. Read `NOTIFICATIONS_FIX.md` for the Somali
installation guide, delivery behavior, and verification results.

This edition includes the green-and-orange dashboard, redesigned navigation and
login, grouped survey editors, and responsive layouts. See `UI_REFRESH_NOTES.md`
for the visual changes and browser verification. No additional database migration
is required for the interface changes themselves.

This build repairs survey integration, migrations, form/document approvals,
permissions, payment validation, and first-time setup. See `REVIEW_REPORT.md`
for the changes and verification results. Historical release notes are in `docs/`.

## New local installation (Windows)

Use the extracted `erp_work` directory. This release was tested on Python 3.10.5.

```powershell
python -m venv env
.\env\Scripts\python.exe -m pip install -r requirements.txt
.\env\Scripts\python.exe run.py
```

Open http://127.0.0.1:5000. On a new SQLite installation, the launcher creates
`.env` with a unique secret, applies migrations, and seeds an administrator and
reference data. Save the temporary administrator password printed in the terminal;
it is displayed only when the account is created. Existing administrator passwords
are preserved. To choose credentials before first setup, set `INITIAL_ADMIN_EMAIL`
and `INITIAL_ADMIN_PASSWORD` (at least 12 characters).

The local server binds to `127.0.0.1` with debug disabled. For deliberate LAN
access set `HOST=0.0.0.0`. Use `serve_waitress.py` for a Windows application server;
configure production environment variables and apply migrations before starting it.
PDF exports use WeasyPrint in an isolated process and require its native runtime
dependencies on the host. If that renderer is unavailable or crashes, the export
opens a printable report with a Print / Save as PDF button; the ERP stays running.

## Upgrade an existing installation

1. Back up the database, `.env`, and uploaded files; stop the running application.
2. Replace application code with this build, preserving those data/configuration files.
3. Activate the application's Python environment and install `requirements.txt`.
4. For an Alembic-managed database run:

```powershell
python -m flask --app wsgi db upgrade
```

5. Restart the application. The current migration revision is `b20k0000a002`.
6. In Admin → User Form Permissions, grant **Solar Pumping Site Survey** permissions
   to the appropriate users. Access is not copied from another form automatically.

Process environment variables now take precedence over `.env`. Check which source
contains your intended database URL before upgrading. For an unstamped legacy SQLite
installation, `python run.py` retains the existing recognized-schema onboarding flow
and creates a backup before stamping; it stops for an unrecognized database.
For legacy PostgreSQL use the existing deployment/legacy schema bridge guidance.
Do not stamp an unknown schema as the current head.

`python init_db.py` now uses Alembic and seeds missing reference data. It does not
reset existing administrator credentials. It is no longer a substitute for legacy
schema onboarding.

## Workflow changes

- New forms and documents start as Draft or Submitted. Payroll batches follow the
  same rule; approval is a separate action.
- Editing a form resets it to Draft, clears the prior reviewer, and records history.
  Changing evidence reopens affected completed milestones for review.
- Payment amounts are rounded to cents before validation. Invalid values, overpayments,
  and payments against unapproved payroll are rejected. The final cent remains due.
- Toggle, remove, approval and notification-send actions use CSRF-protected POST forms.
- Pumping projects use the pumping survey as their default survey requirement.
  Other project types use the combined off-grid survey/load assessment. Existing
  custom evidence links and completed historical milestones are preserved.
- Legacy load assessment records remain available, but are not an extra required
  form in the current completion checklist.

## Run tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests migrate disposable SQLite databases and keep uploads in temporary directories.
The optional PostgreSQL check runs only when `TEST_POSTGRES_URL` is configured for
a dedicated test database. Live email, WhatsApp and AI services are not exercised.
