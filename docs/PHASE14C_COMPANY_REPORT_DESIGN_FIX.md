# Phase 14C - Company Profile, Material Reports Menu and Design Fix

Fixed:
- Added Material Reports page under Materials menu.
- Added Company Profile table and Admin form.
- Company name/details now available to forms and reports through `company_profile`.
- Login default admin/password text removed.
- Cadceed-Maal orange/green design applied to navigation, cards, tables, buttons and login.
- Global Close / Back and Home buttons added to pages so forms are not trapped.
- Form print and PDF report templates now use company details instead of hard-coded company text.

Test:
1. Copy old `instance/solar_documents.db` into this folder.
2. Run `python init_db.py`.
3. Run `python run.py`.
4. Open Admin → Company Profile.
5. Open Materials → Material Reports.
