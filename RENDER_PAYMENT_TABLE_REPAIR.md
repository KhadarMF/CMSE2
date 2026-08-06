# Render repair: missing payment_request table

This package contains additive migrations `b20h0000a002` and `b20h0000a003`.
The first repairs a legacy
database whose Alembic history was stamped even though the payment request
tables were absent. The second makes obsolete required fields optional in old
SQLite payment tables, allowing new requests without deleting legacy data.

## Deploy

1. Keep the downloaded database backup in a safe location.
2. Copy this package into the local GitHub `CMSE2` repository.
3. Commit and push the changed files, including the `migrations/versions`
   folder.
4. In Render, set **Pre-Deploy Command** to:

   ```text
   flask db upgrade
   ```

5. Choose **Manual Deploy -> Deploy latest commit**.
6. The deploy log should contain:

   ```text
   Running upgrade b20h0000a001 -> b20h0000a002
   Running upgrade b20h0000a002 -> b20h0000a003
   ```

7. Open a project and test Payment Requests and Team Daily Reports.

Do not run `init_db.py` against the existing Render database. The repair
creates only missing payment tables and does not delete existing records.
