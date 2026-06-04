# Phase 14B - Menu, Compact Datasheet Forms, Reference Numbers, Back/Close Buttons

Fixed:
- Materials now has its own main menu.
- Material Request form changed to compact datasheet layout.
- Material Return form changed to compact datasheet layout.
- Warehouse Issue form made compact.
- Added Back / Close / Home buttons so forms are not trapped.
- Materials forms and reports show reference numbers.
- Online forms show generated reference numbers without changing old database schema.
- Project material report shows Report Ref.

Run:
1. Copy old instance/solar_documents.db into this folder.
2. env\Scripts\activate
3. python init_db.py
4. python run.py
