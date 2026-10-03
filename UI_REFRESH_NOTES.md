# Solar ERP visual refresh

## Waxa cusub

- Dashboard cagaar deggan leh, xog-koobyo cad iyo badhamo oranji ah.
- Menu dhinaca bidix oo astaamo isku mid ah iyo bogga hadda furan tilmaamaya.
- Bog gelitaan cusub, calaamado cad iyo badhan lagu muujiyo/qarin karo password-ka.
- Liiska foomamka oo kaarar leh; sahan kasta wuxuu leeyahay sharaxaad iyo tirada diiwaannada.
- Sahannada off-grid iyo pumping, iyo warbixinta maalinlaha ah, oo qaybo loo kala saaray.
- Tirinta meelaha la buuxiyey iyo badhan kaydin oo muuqda inta foomka la rogayo.
- Muuqaal telefoon oo hal saf ah iyo jadwallo dhinaca loo rogi karo.

## Installation and scope

This ZIP is the complete reviewed Phase 20K application plus the visual refresh.
Follow README.md for installation or upgrade. The UI changes introduce no new
database migration or Python dependency. When upgrading from the original Phase
20K archive, follow the README migration instructions for the included backend fixes.
Restart the application and refresh the browser after replacing the code.

Keep your existing database, uploaded files and .env when upgrading. Preview data,
preview credentials and local test databases are not included. Screenshots use
fictional demonstration projects and do not show the user's live records.

The form completion indicator counts filled fields; it does not autosave or certify
that a survey is complete. Use Save form / Update form to persist changes.
Existing roles, form permissions, approval actions and server-side filters are retained.
The interface retains the application's English labels and existing Somali option
translations. This release does not introduce a full Somali translation.

Styling is centralized in app/static/css/refresh.css. Inline SVG icons need no
icon-font service; Bootstrap still loads from the existing jsDelivr CDN.
The PDF renderer behavior and fallback described in REVIEW_REPORT.md are unchanged.

## Verification — 12 September 2026

- Regression suite: 64 passed, 1 skipped, 1 deselected. PostgreSQL integration was
  skipped without a test DSN; the native PDF export test was excluded from this UI
  run because it was already checked during the backend review.
- Final targeted dashboard, form and project-context tests: 8 passed.
- All 119 configured fields across eight form types are preserved exactly once.
- Browser checks: login, forms library, both survey editors, off-grid survey save
  and reopen, customer display, filled-field count, mobile menu open/close and Escape.
- Desktop 1440 x 960 and mobile 390 x 844 checks found no page-level horizontal
  overflow; wide dashboard tables scroll within their containers.
- No browser JavaScript errors or warnings were observed during the checked flows.

Verification used an isolated local SQLite database. The live installation was not
modified or deployed by this task. See REVIEW_REPORT.md for backend findings and limits.
