# Phase 17B.2G — Admin Account Recovery

Purpose: recover the ERP Admin account without deleting or changing business data.

## What changed
- Added `app/admin_recovery.py`.
- Added `recover_admin.py` one-off recovery command.
- Added optional environment-variable based recovery on app startup.

## Safe recovery option for Render
1. Open Render → Web Service → Environment.
2. Add:
   - `ADMIN_RECOVERY_EMAIL=admin@cadceedmaal.com`
   - `ADMIN_RECOVERY_PASSWORD=<your-new-strong-password>`
3. Save and redeploy.
4. Login using `admin@cadceedmaal.com` and the new password.
5. Remove `ADMIN_RECOVERY_PASSWORD` from Render Environment.
6. Redeploy once again.

## Alternative Render Shell command
If Render Shell is available:

```bash
python recover_admin.py admin@cadceedmaal.com 'NewStrongPassword123!'
```

## Data safety
This recovery only resets or creates the Admin login account. It does not delete customers, projects, quotations, documents, WhatsApp logs, permissions, or any other business data.
