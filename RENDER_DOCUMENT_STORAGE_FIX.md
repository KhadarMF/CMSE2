# Render Document Storage Fix

## What changed

- The Phase 20I data migration now emits PostgreSQL `TRUE/FALSE` values instead
  of an integer `1` for Boolean milestone requirements. This fixes the Render
  pre-deploy `DatatypeMismatch` failure.
- A missing uploaded file no longer opens a raw `404 Not Found` page.
- The document page shows `File missing` beside unavailable versions.
- The user can select `Upload replacement` to restore the document.
- Existing document downloads continue to return the original file normally.
- No database schema or existing database records are changed by this fix.

## Render configuration

Uploaded documents must use persistent storage. On the existing Render web
service, attach a persistent disk and use:

- **Mount path:** `/var/data/uploads`
- **Environment variable:** `UPLOAD_FOLDER=/var/data/uploads`

Then deploy the latest Git commit. Do not replace or recreate `DATABASE_URL`.

Files already lost from Render's temporary filesystem cannot be rebuilt from
their database records. Open the affected document and use `Upload replacement`
with the original file.

## Verification

The automated tests cover both an available version download and a missing
version after a deployment/restart.

