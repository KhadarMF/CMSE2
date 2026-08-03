# Phase 20A/20B – Accounting: Chart of Accounts + Double-Entry Journal Engine

## Scope
Double-entry accounting foundation (20A) plus automatic journal entries from the modules that already move money (20B). The ledger runs in one base currency (USD); SLSH transactions convert at a configurable rate. Reports beyond the per-account ledger (Trial Balance, P&L, Balance Sheet, opening balances) are Phase 20C — deliberately not in this drop.

## The two rules this module is built on
1. **Every posted entry balances.** `sum(debits) == sum(credits)`, enforced in `app/accounting_service.py` at posting time. An unbalanced entry cannot be posted, through the UI or through code.
2. **Posted entries are immutable.** No edit, no delete — corrections are reversal entries (`create_reversal`), which create a new posted entry with debits/credits swapped and link both directions. Both stay in the ledger and net to zero, so the audit trail is complete. Only Draft entries can be edited or deleted. If either rule is ever weakened, the ledger stops being trustworthy — don't.

## Added
- **Models** (`app/models.py`): `Account` (code, name, type, parent hierarchy, `is_system` flag protecting seeded accounts), `JournalEntry` (entry_no `JE-YYYYMMDD-000001`, status Draft/Posted/Reversed, source tracking, currency + exchange_rate + original_amount, reversal linkage in both directions), `JournalLine` (USD debit/credit per account), `AccountMapping` (business event → ledger account).
- **Service** (`app/accounting_service.py`): the only path for journal creation — `create_journal_entry` (all validation), `post_entry`, `create_reversal`, `account_balance` (natural-sign balances from Posted+Reversed entries), seeding, and the two auto-journal builders. `try_auto_journal` wraps route hooks so a journal failure can never undo the business record it describes.
- **Seeded chart of accounts** (24 accounts): Cash/Zaad/E-Dahab/Bank, AR, Inventory, Fixed Assets, AP, Loans, Owner's Equity, Opening Balance Equity, Sales/Service/Other revenue, and an expense account per payment-request category. Seeding fills gaps only — accountant customizations are never overwritten.
- **Routes + templates** (`app/routes/accounting_routes.py`, `app/templates/accounting/`): dashboard (type totals, cash & mobile-money balances, drafts alert), Chart of Accounts, account create/edit, per-account ledger with running balance, journal list/detail, manual journal form (dynamic lines, live balance check, post or save-as-draft), post/reverse/delete-draft actions, Mappings & Settings.
- **Automation (20B)**:
  - Payment Request payment recorded → Debit expense account mapped to the request's category, Credit asset account mapped to the payment method. Posted automatically.
  - Payroll payment recorded → Debit Salaries & Wages, Credit the method's asset account.
  - Both hooks run **after** the payment commits: the payment is the source of truth; if the journal fails (e.g. missing SLSH rate), the payment stands and a warning tells the user to add the journal manually.
- **Mappings page**: category→expense account, method→asset account, payroll salaries account, and the SLSH-per-USD rate. All automation account choices live here, never in code.
- **Currency**: line amounts are always USD. SLSH payments convert at the configured rate; each entry stores the rate and original amount it was booked at, so changing the rate later never rewrites old entries. **If no rate is set, SLSH auto-journals are skipped with a warning rather than booked at a made-up rate.**
- **Permissions**: new key `accounting` (Finance category) in `FORM_PERMISSION_KEYS`, all endpoints mapped in `permission_enforcer.py`. On top of the form-permission grant, posting/reversing/mapping changes require a finance-tier role (Admin, Management, Finance Officer) — a view-only grant really is view-only.
- **Nav**: Accounting, Chart of Accounts, Journal, Mappings & Settings added to the Finance section, individually gated.

## Design decisions worth knowing
- **Account code and type lock once an account has journal history.** Changing them would silently rewrite every past report. Name/description stay editable; system accounts can't be deactivated because automation mappings point at them.
- **Payroll amounts are treated as USD** — the payroll module has no currency field. If you ever pay payroll in SLSH, that's a payroll-module change first.
- **Reversed entries still count in balances** together with their reversals (netting to zero) — that's correct double-entry behavior, not a bug.

## Before this is usable
1. **Grant permissions**: Admin → Form Permissions → "Accounting". `can_view` for viewers; finance users doing real work need `can_view + can_create + can_edit + can_approve + can_delete` (delete only ever applies to drafts — posted entries are protected by the immutability rule regardless of grants).
2. **Set the SLSH rate** in Accounting → Mappings & Settings if you record SLSH payments.
3. **No migration step** — tables lazy-create and the chart seeds on first request, same convention as the other modules. If you hit a "no such column" error like Phase 19's, it means a table was created mid-copy with a stale schema; say so and I'll give you the same style of one-time fix script.
4. Journals only capture payments made **after** this deploys. History from before, and your existing cash balances, go in later via opening balances (20C) or manual entries.

## Not built (explicitly)
- Trial Balance, P&L, Balance Sheet, opening balances — Phase 20C.
- Sales-side automation: the sales module has no "money received" event to hook (quotations aren't payments). Needs an invoice/receipt concept first.
- Multi-currency ledger with revaluation and FX gains/losses. Period closing/locking. Budgets, AR/AP aging, depreciation, tax.

## Testing
16 automated checks (deleted before packaging): seeding; unbalanced/invalid entries rejected; posting and natural-sign balances on both sides; posted-entry delete blocked; reversal linkage, net-to-zero, double-reversal blocked; payment-request auto-journal hits the right accounts; SLSH without rate → payment succeeds, journal skipped with warning; SLSH with rate → converts correctly, stores rate + original; payroll auto-journal; manual journal form (empty rejected, draft, post); view-only role blocked from posting/reversing; ungranted user denied and nav hidden; all pages render; ledger running balance; history-locked account edit rules. Plus a restore-engine test confirming Phase 18A.4 handles the four new tables with zero changes, and a regression pass over dashboard/payments/payroll/backup/restore.

## Not changed
Payment Requests and Payroll got only the post-commit journal hooks (payment behavior identical, including on journal failure). Backup/Restore untouched. `models.py` additions are purely appended; one tuple added to `FORM_PERMISSION_KEYS`.
