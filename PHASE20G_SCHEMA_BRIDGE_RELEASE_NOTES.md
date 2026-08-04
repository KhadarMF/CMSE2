# Phase 20G — Legacy Database Schema Bridge

## What this fixes

Phase 20F code can fail on an older database with an error such as:

```text
sqlalchemy.exc.OperationalError: no such column: payment_request.requested_by_id
```

The older database already has a `payment_request` table, but that table uses
the former Payments/Accounting schema. An Alembic baseline stamp does not
change a table which already exists, so a normal Phase 20D upgrade could leave
the old columns in place.

Revision `b20g0000a001` bridges that schema safely. It preserves legacy data,
adds and backfills the current payment fields, copies the old chart of accounts
to the current account table, repairs journal references, and creates payment
history rows for legacy requests already marked Paid.

Legacy-only tables and columns are intentionally retained; the migration does
not discard historical business data.

## Before upgrading

1. Stop the local Flask server.
2. Keep a copy of `instance/solar_documents.db` somewhere outside the project.
3. For Render/PostgreSQL, create and download a fresh application/database
   backup before deploying this release.

Do **not** run `init_db.py` against an existing database.

## Existing local SQLite database

Open PowerShell in the project folder and activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

If the database has never used Alembic (there is no `alembic_version` table),
run:

```powershell
python -m flask db stamp cc82184d6822
python -m flask db upgrade
```

If it is already stamped, run only:

```powershell
python -m flask db upgrade
```

Then start the app:

```powershell
python run.py
```

## Render/PostgreSQL

The permanent Render **Pre-Deploy Command** must be:

```text
flask db upgrade
```

Push this release to the repository connected to Render, then deploy the
latest commit. A production database already upgraded to Phase 20D will move
from `b20d0000a001` to `b20g0000a001` automatically.

After deployment, confirm the log contains:

```text
Running upgrade b20d0000a001 -> b20g0000a001
```

Then test:

- `/health`
- one project detail page
- Payment Requests
- Accounting Dashboard

## Verification performed for this release

- Upgrade from a copy of the reported 63-table SQLite database: passed.
- Upgrade from a fresh empty database: passed.
- Legacy paid payment request, attachment, and reference preservation: passed.
- Project detail, Payment Requests, and Accounting pages after migration:
  HTTP 200.
