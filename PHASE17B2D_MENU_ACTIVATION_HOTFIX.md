# Phase 17B.2D – Menu Activation & Navigation Consistency Hotfix

## Purpose
This hotfix improves navigation usability without touching authentication, session, database, or core permission engine.

## Changes
- Added Dashboard Main Navigation quick-launch cards.
- Quick-launch cards are only shown when the user has permission, and all shown cards are clickable.
- Admin sees all main navigation areas as active/clickable.
- Improved sidebar active-state detection using exact match and child URL prefix matching.
- Parent sidebar sections auto-expand and highlight when a child page is active.
- Removed dark-looking inactive dashboard quick access style.
- Added hover/active styling so clickable navigation is clearer.

## Security
- No authentication/session code was changed.
- No database schema changes.
- No permission engine changes.

## Test Checklist
1. Login as Admin.
2. Dashboard shows Master Data, Sales, Projects, Operations, Reports, AI Center, System as clickable cards.
3. Click each card and confirm it opens the correct page.
4. Open Customers and confirm Master Data expands and Customers is active.
5. Open Quotations and confirm Sales expands and Quotations is active.
6. Logout and confirm login is still required.
