# Phase 15N - Template & Permission Display Fix

Fixes:
- Dashboard TemplateSyntaxError caused by extra `{% endif %}`.
- Project full report Jinja expression syntax error.
- Dashboard quick access buttons are now hidden unless the user has permission.
- Dashboard task/document sections are permission-aware.

Test:
1. Copy old `instance/solar_documents.db` from Phase 15M into this folder.
2. Run `python init_db.py`.
3. Run `python run.py`.
4. Login as Admin and set permissions.
5. Logout/login as the restricted user.
