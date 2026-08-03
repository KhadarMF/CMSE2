# Phase 18A.1 – Backup Foundation

## Purpose
Introduces a PostgreSQL/Render compatible Backup & Maintenance Center.

## Added
- New `app/backup_service.py` backup engine.
- PostgreSQL detection and `pg_dump` support when available.
- JSON and CSV database export fallback for Render environments without `pg_dump`.
- Uploads/files backup inside the ZIP package.
- `manifest.json` and `backup_info.json` metadata files.
- SHA256 checksum for each backup.
- Backup health check dashboard.
- Backup history with Download, Verify, and Delete actions.

## Changed
- Replaced old SQLite-only backup logic that showed `Database file not found` on Render PostgreSQL.
- Updated `app/templates/admin/backup.html` for Backup & Maintenance Center.
- Updated `app/routes/admin_routes.py` backup routes only.

## Not Changed
- Login/authentication not changed.
- Sessions not changed.
- Permissions not changed.
- Customer 360 not changed.
- Database schema not changed.
- Restore not implemented yet.

## Testing
1. Login as Admin.
2. Go to System → Backup.
3. Confirm Database shows PostgreSQL on Render.
4. Click Create Backup.
5. Download the generated ZIP.
6. Click Verify.

## Important
Restore is intentionally deferred to a later phase after backup creation is stable.
