# Phase 18A.4 – Restore Engine

Built on Phase 18A.3.

## Added
- Restore Center page (`/admin/restore`): lists backups with a Restore action, shows lock/maintenance status and recent restore activity.
- Restore confirmation screen (`/admin/restore/confirm/<filename>`): table-by-table row comparison between the backup and the live database, restore mode selection, files toggle, and a type-the-filename confirmation before anything runs.
- Restore route (`/admin/restore/execute/<filename>`, POST): validates the confirmation text, dispatches to the selected restore mode, flashes a result, redirects to the restore log entry.
- Backup verification is mandatory before restore: `verify_backup()` (from 18A.3) runs first and blocks restore if it fails, no override.
- Automatic pre-restore backup: every restore attempt creates a safety backup labeled "Before Restore" before touching anything.
- Data restore (`json_data`, default): deletes and re-inserts every table's rows from the backup's `database.json`, inside a single transaction on a dedicated connection. Any failure rolls back cleanly — the live database is left exactly as it was. Works for PostgreSQL and SQLite, and across engines (e.g. a SQLite backup restored into a PostgreSQL deployment).
- SQLite file restore (`sqlite_file`): exact binary replace of the live `.db` file from the backup's `database.sqlite3`, using copy-to-temp-file + atomic rename rather than an in-place overwrite.
- PostgreSQL full SQL restore (`postgres_sql`): drops and recreates the `public` schema, then loads the backup's `pg_dump` file via `psql`. Requires an explicit extra checkbox on the confirmation screen — this mode replaces the schema, not just the data.
- Restore log: every restore attempt (success or failure) is written to `backups/restore_logs/*.json` on disk, independent of the database, so the log survives even a restore that replaces the database. Log list and detail pages at `/admin/restore/log`.
- Maintenance mode: while a restore is running, every request except the Restore Center itself gets a 503 maintenance page (`app/templates/system/maintenance.html`). Backed by a lock file (`backups/RESTORE_IN_PROGRESS.json`) that also blocks a second concurrent restore from starting.
- `create_backup()` now accepts a `label` (Manual / Before Restore) and writes it into `manifest.json`.
- Backup filenames now use microsecond-resolution timestamps, with an additional existence check that appends a numeric suffix on collision. See "Fixed" below — this replaces a real bug, not a hypothetical one.

## Fixed
- **Backup filename collision (confirmed, not hypothetical):** `create_backup()` previously stamped filenames with second-resolution timestamps (`%Y%m%d_%H%M%S`). Two backups created within the same second got the same filename, and since the zip is opened in write/truncate mode, the second one silently overwrote the first. This was caught during testing of the automatic pre-restore backup: the safety backup landed in the same second as the backup being restored from and overwrote it mid-restore, so the "restore" silently restored from the now-mutated safety backup instead of the original. Fixed with microsecond-resolution timestamps plus a defensive existence check in `create_backup()` that appends a numeric suffix if a collision is somehow still possible. In real usage (an admin clicking through the UI) this needed two backups within the same second to trigger, which is unlikely by hand — but the automatic pre-restore backup made it a normal, expected occurrence, and the failure mode (restoring from the wrong data with no error raised) was severe enough to fix outright rather than note as a caveat.

## Changed
- `app/templates/admin/backup.html`: added a Restore Center link and a per-row Restore action; the "restore not implemented" notice is replaced with a pointer to the Restore Center.
- `app/templates/base.html`: added a Restore nav item next to Backup.
- `app/permission_enforcer.py`: mapped the new restore endpoints to the existing `backup` permission key (Admin-only), and also mapped `admin.verify_backup` / `admin.delete_backup`, which were missing a mapping in 18A.3.
- `app/__init__.py`: added the maintenance-mode `before_request` hook.
- `BACKUP_VERSION` bumped to `18A.4`.

## Not changed
- Login/authentication, permissions engine, Customer 360, navigation structure, database schema (except via `postgres_sql` restore mode, which is opt-in and explicitly warned about).

## Known limitations — read before relying on this
- **Single-instance only.** The restore lock and maintenance mode are a file on local disk. They work correctly for one running app instance. If this is ever deployed as more than one Render instance at once (horizontal scaling), a restore on one instance will not put the others into maintenance mode, and they will serve requests against a database that's being rewritten underneath them. Do not scale to multiple instances without revisiting this.
- **Restore runs synchronously inside the HTTP request that triggers it.** There is no background job queue in this app. For a large database, this risks hitting Render's or gunicorn's request timeout before the restore finishes, which would leave the restore in an unknown state (the lock file would need manual cleanup). This is fine at your current data size; worth revisiting if the database grows substantially.
- **No CSRF protection anywhere in this app**, including the new restore form. The typed-filename confirmation is a UI safety net against misclicks, not a security control — it does not stop a forged cross-site request from a browser with an authenticated session. This was already true of every other POST in the app (delete backup, delete user, etc.); it matters more here given what restore can do. Consider adding Flask-WTF's CSRFProtect as a follow-up phase; it touches every form template, so it's its own piece of work.
- **`postgres_sql` mode can desync the live schema from the app's code.** It restores the schema exactly as it was at backup time. If models.py has gained columns or tables since that backup, the app will error until `create_tables.py` (or a proper migration) is re-run. `json_data` mode does not have this problem, since it only touches data, never schema.
- **File restore is a merge, not a mirror.** Restoring uploaded files copies the backup's files into the live uploads folder, overwriting same-named files, but does not delete files that exist live but aren't in the backup. A full point-in-time restore of uploads would need to clear the folder first; that was left out because it's a more destructive default than the rest of this phase, and is easy to add later if wanted.

## Testing
Automated (not part of the shipped code — delete after running):
1. Login as Admin, create a backup, confirm no two backups ever share a filename even created back-to-back.
2. Mutate a row, restore via `json_data`, confirm the mutation is reverted and the transaction rolled back correctly on induced failure.
3. Mutate a row, restore via `sqlite_file` ten times back-to-back, confirm 10/10 success (this mode failed intermittently before the filename-collision fix above — the flakiness was the collision, not the file-swap itself, which was independently verified byte-for-byte correct throughout).
4. Confirm a second restore attempt is refused while one is "in progress" (simulated lock).
5. Confirm every other route returns 503 with the maintenance page while a restore is in progress, and returns to normal once the lock is released.
6. Corrupt a backup file and confirm restore is blocked both in the preview (`can_restore = False`) and if attempted directly.

Manual, before trusting this in production:
1. Login as Admin → System → Restore.
2. Restore a small backup with `json_data` mode, confirm the table diff on the confirmation screen looks right before typing the filename to confirm.
3. Check `/admin/restore/log` and open the detail page for that attempt.
4. On Render specifically: confirm `psql` is not installed (it likely isn't) so `postgres_sql` mode correctly shows as unavailable, and confirm `json_data` mode still works there via the JSON/CSV export path, same as backup creation already does.
