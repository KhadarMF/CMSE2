# Dashboard Command Center V5

## What changed

The general dashboard is now a role-aware company command center instead of a
collection of disconnected totals. It reads existing operational records and
does not create a second dashboard database.

- Consistent, fully clickable KPI cards with semantic colors and navigation.
- Filters for project, branch, project status, and as-of date.
- Portfolio progress: overall, physical, financial, procurement, documents,
  schedule, risk, and project health.
- Attention Required list for critical issues, overdue tasks, delayed projects,
  missing daily reports, approvals, and material requests.
- Project Portfolio 360 comparison table.
- Financial overview for authorized Admin/Management/Finance users only.
- Document/form approval, operations, procurement, task, and data-quality views.
- Data-driven AI Executive Summary with recommended actions.
- Excel-friendly CSV export and Print/PDF support.
- Team Leaders see only projects assigned to teams they lead. Financial totals
  remain hidden unless a separate finance/accounting permission grants access.
- Responsive desktop and mobile layout.

## Database

Dashboard V5 adds no database table or column. This full package still includes
the earlier Phase 20H repair migrations through `b20h0000a003`, so always keep
the normal Render migration step enabled.

## Local installation

1. Back up the existing database.
2. Copy the release files over the local CMSE2 repository, preserving the
   folder structure, including `migrations`.
3. Do not copy or replace `.env` or the production database.
4. From the project folder run:

   ```powershell
   python -m flask db upgrade
   python run.py
   ```

5. Open `/dashboard` and test the cards, filters, project links, and CSV export.

Do not run `init_db.py` against an existing database.

## Render deployment

1. Download a fresh application/database backup first.
2. Copy the release files into the local GitHub `CMSE2` repository.
3. In GitHub Desktop, commit with a message such as
   `Dashboard Command Center V5`, then click **Push origin**.
4. Keep Render **Pre-Deploy Command** as:

   ```text
   flask db upgrade
   ```

5. In Render choose **Manual Deploy > Deploy latest commit**.
6. Wait for **Live**, then test `/dashboard` using an Admin and a Team Leader.

Do not run `flask db stamp` on every deploy, and do not run `init_db.py` against
the existing Render database.

## Verification

- Automated suite: 37 passed, 1 skipped.
- Desktop visual check: passed.
- Mobile responsive check at 390 x 844: passed.
- Admin CSV export: passed.
- Team Leader project scoping and financial-data hiding: passed.
