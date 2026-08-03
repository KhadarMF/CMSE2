# Phase 20C – Financial Reports + Opening Balances

## Scope
Trial Balance, Profit & Loss, Balance Sheet, and an Opening Balances entry screen. **No new tables, no schema change** — every report is computed from posted journal entries, and opening balances are a normal posted journal entry (`source_module = "opening-balances"`) going through the same engine as everything else. The immutability rule from 20A is what makes these reports trustworthy: nothing they read can be silently edited afterwards.

## Added
- **Trial Balance** (`/accounting/reports/trial-balance`): every account with activity, net balance in a Debit or Credit column, totals at the bottom. Optional as-of date. If the totals ever disagree, the page says so in red instead of hiding it — with posted-only entries that should be impossible, so it doubles as a ledger integrity check.
- **Profit & Loss** (`/accounting/reports/income-statement`): Income and Expense sections with a date range filter, net profit/loss highlighted.
- **Balance Sheet** (`/accounting/reports/balance-sheet`): Assets vs Liabilities + Equity as of a date. Equity includes a computed **"Current Earnings"** line (all income minus expenses up to the date) — there is no period-closing in this system, so earnings are always carried as this computed line rather than closed into retained earnings. The A = L + E check is shown and flagged loudly if broken.
- **Opening Balances** (`/accounting/opening-balances`): enter Asset/Liability/Equity balances as of your start date, on each account's natural side (positive Cash = you have it, positive Loan = you owe it, negative flips). The balancing difference goes automatically to **3100 Opening Balance Equity**. Posts one journal entry immediately. A warning shows if opening balances were already posted — posting again adds on top, it does not replace; reverse the earlier entry first if correcting.
- All report pages have a Print button (browser print; filter forms and navigation are hidden in print).
- Nav: Trial Balance, Profit & Loss, Balance Sheet added to the Finance section; Opening Balances reachable from the Accounting dashboard (finance-tier only).

## Design notes
- Reversed entries and their reversals both count in every report (netting to zero) — correct double-entry behavior, verified by test.
- Income/expense accounts have no opening balances by design; they measure a period, not a position.
- Reports respect the existing role model: any `accounting` view grant can read reports; posting opening balances requires the finance tier (Admin/Management/Finance Officer).

## Not built (explicitly)
- Period closing / year-end close (earnings stay as the computed line).
- PDF export (browser print covers it for now; WeasyPrint export can be a small follow-up if needed).
- Comparative periods (this month vs last month), cash-flow statement, drill-down date filters on the ledger view.

## Testing
11 automated checks (removed before packaging): opening-balance natural-side math and OBE plug; empty-input rejection; duplicate-entry warning; P&L totals over all entries and over a bounded range (out-of-range entries excluded); trial balance totals equal with per-account spot checks; balance sheet equation including current earnings, both unbounded and as-of a mid-year date; all three reports remain balanced and correct after a reversal; all pages render with and without filters; view-only user blocked from posting opening balances; nav links gated. Plus a 13-page regression pass across payments, payroll, backup/restore, and all accounting pages. Two clean repeat runs, identical results.

## Not changed
20A/20B engine, automation hooks, Payment Requests, Payroll, Backup/Restore. `accounting_service.py` and `accounting_routes.py` got purely appended sections; `permission_enforcer.py` got four new endpoint mappings; dashboard/base templates got links.
