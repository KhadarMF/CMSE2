# Phase 16C - Save Forms & Quotation Edit Fix

## Fixes

1. **Save Forms Internal Server Error**
   - Added PostgreSQL sequence auto-sync on app startup.
   - Fixes duplicate primary key errors after database import/restore, such as `duplicate key value violates unique constraint`.
   - Applies to projects, forms, quotations, tickets, and other tables with integer `id` primary keys.

2. **Quotation Open/Edit Flow**
   - Quotations list now has:
     - **Open / Edit** button: opens editable quotation form.
     - **Report** button: opens printable quotation report.
   - Added full quotation edit route: `/sales/quotations/<id>/edit`.
   - Existing quotation lines can be edited and saved.
   - Added **Edit Form** button inside quotation report page.

## Deployment

Copy this version to the CMSE2 GitHub repo, commit, push, then deploy on Render.
