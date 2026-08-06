# Local repair: legacy payment request constraints

If local SQLite reports `NOT NULL constraint failed:
payment_request.request_date`, apply migration `b20h0000a003`.

1. Stop the local server with `Ctrl+C`.
2. Keep `instance/solar_documents.db`; do not replace or delete it.
3. Make sure this file exists in the application:

   ```text
   migrations/versions/b20h0000a003_phase20h_relax_legacy_payment_fields.py
   ```

4. From the application's terminal, run:

   ```powershell
   python -m flask db upgrade
   ```

5. Start the application again:

   ```powershell
   python run.py
   ```

The migration preserves the legacy fields and data. It only makes the
obsolete `request_date`, `payment_type`, and `created_by_id` fields optional,
because the current workflow uses their replacements.
