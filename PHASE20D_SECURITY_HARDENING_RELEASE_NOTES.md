# Phase 20D — Security & Data Integrity Hardening

No new business features. This release fixes the problems found in the
Phase 20C code review, all of which had to be closed before Phase 21
(Sales Invoices / Purchases) could safely be built on top.

**Deployment is not automatic. Read `deployment_render.md` first.**

---

## 1. CSRF protection restored

**Was:** no CSRF protection anywhere. `Flask-WTF` was not installed and
`CSRFProtect` was never initialised. Any logged-in user who opened a
malicious link could have a payment request approved, a journal entry
posted, or a user's password changed without knowing it. Given that Phase 19
moves real money over Zaad and eDahab, this was the most serious hole.

**Now:** `CSRFProtect` is enabled globally in `app/security.py:init_csrf()`.

| | |
|---|---|
| Templates patched | 69 |
| POST forms given a token | 87 |
| POST routes now protected | 89 |
| AJAX/fetch calls needing rework | 0 |

The zero in the last row is why this was safe to do in one pass: the app is
entirely server-rendered, so no JavaScript had to be touched.

**Exemption:** `/whatsapp/webhook` is exempt. Meta's servers post to it with
no browser session and therefore no token; it is authenticated separately by
the verify token. This is the one endpoint where CSRF would have broken a
working integration.

**Also fixed:** `/admin/backup/create` accepted `GET`. A state-changing GET
can be fired by a bare `<img src>` on any page and is not covered by CSRF
protection. It is now POST-only.

**Why this did not break everything the way V49→V50 did:**
`tests/test_forms_still_work.py` drives real forms end to end with CSRF ON —
a login and an account creation, all the way to the database — plus a static
sweep that fails the build if any POST form in any template is missing a
token.

---

## 2. SECRET_KEY no longer falls back to a placeholder

**Was:** `os.environ.get("SECRET_KEY", "change-this-secret-key")`. If the
environment variable were ever missing on Render, the app would boot happily
using a secret that is published in the source code — and anyone who read
it could forge a session cookie for any user, including Admin.

**Now:** `validate_secret_key()` raises `RuntimeError` at startup in
production if the key is missing, is a known placeholder, or is shorter
than 32 characters. A crash on boot is far cheaper than a silent compromise.

Development is unaffected: set `FLASK_ENV=development` and the check is
skipped.

**Related:** `SESSION_COOKIE_SECURE` used to be opt-in, which in practice
meant "off because someone forgot the variable". It now defaults to ON in
production.

> **Deployment note:** changing SECRET_KEY invalidates every existing
> session. All staff will be logged out once. Tell them the day before.

---

## 3. Login throttling

**Was:** unlimited login attempts. A script could guess passwords
indefinitely with nothing to stop it.

**Now:** every failed attempt is recorded in a new `login_attempt` table and
checked *before* the password is verified, so a locked-out attacker learns
nothing from response timing.

| Limit | Default | Env variable |
|---|---|---|
| Failures per email | 5 | `LOGIN_MAX_ATTEMPTS_PER_EMAIL` |
| Failures per IP | 20 | `LOGIN_MAX_ATTEMPTS_PER_IP` |
| Rolling window | 15 min | `LOGIN_WINDOW_MINUTES` |
| Lockout duration | 15 min | `LOGIN_LOCKOUT_MINUTES` |

Two deliberate design choices:

- **Both email and IP are tracked.** Email-only lets an attacker lock a real
  colleague out on purpose; IP-only lets a botnet spread guesses across
  addresses.
- **The real client IP is read from `X-Forwarded-For`.** Render terminates
  TLS at a proxy, so `request.remote_addr` is the proxy for every user — the
  IP limit would have locked out the whole company at once.

A successful login clears that email's counter. If the throttle table is
unreachable the check **fails open**, because a broken counter must never
lock the company out of its own ERP.

---

## 4. Money is now exact

**Was:** every money column was `db.Float` — 29 of them, zero `Numeric`.
Binary floating point cannot represent 0.01 exactly, so repeated addition
drifts. Eventually the trial balance shows a cent that nobody can trace to
a transaction, and the Finance Officer loses trust in the whole ledger.

**Now:** three custom column types in `app/types.py`:

| Type | SQL | Used for |
|---|---|---|
| `Money` | `NUMERIC(14,2)` | 21 columns — all currency amounts |
| `Quantity` | `NUMERIC(14,3)` | 6 columns — quantities, work days |
| `Rate` | `NUMERIC(18,6)` | 1 column — `journal_entry.exchange_rate` |

These store an exact decimal in the database but hand a plain `float` back
to Python, so **every existing calculation in routes, services and templates
keeps working unchanged.** This was a retrofit, not a rewrite.

Rounding on write is **ROUND_HALF_UP**, not Python's default banker's
rounding. `round(0.125, 2)` in Python gives `0.12`; accountants expect
`0.13`. There is a test for this.

### Backend caveat, stated plainly

SQLite has no true DECIMAL type — it stores `NUMERIC` as an 8-byte float. So
on **local SQLite**, a raw `SELECT sum(debit)` can still drift. Two things
make this acceptable:

1. Production is PostgreSQL, where `NUMERIC` is genuinely exact.
2. The application never reads money with raw SQL — every path goes through
   the ORM types and `account_balance()`, which quantize.

`test_raw_sql_sum_is_exact_on_postgres` verifies the stronger guarantee and
runs when you set `TEST_POSTGRES_URL`. Do run it once against a copy of
production.

### Before you migrate

`preflight_check_20d.py` lists every stored value with more decimal places
than the new column keeps. Converting rounds them. Review the list with the
Finance Officer first — it is normally correct, but you should see it rather
than discover it.

---

## 5. Alembic owns the schema

**Was:** no migration tool. Eight route files called `db.create_all()` at
request time. `create_all()` creates missing **tables** and silently ignores
missing **columns** — so a model change could deploy cleanly and then throw
`UndefinedColumn` at a user hours later. This is how the schema drifted, and
it would have made Phase 21 genuinely dangerous.

**Now:** `Flask-Migrate` / Alembic, with two migrations:

- `cc82184d6822` — baseline, the full 63-table schema
- `b20d0000a001` — Float→Numeric conversion + `login_attempt` table

Every `db.create_all()` call has been removed. Data seeding
(`ensure_default_accounts()`) stays, because that is data, not schema.

The migration is **backend-aware**: PostgreSQL gets
`ALTER TYPE ... USING col::numeric` (required — Postgres will not implicitly
cast double precision to numeric), and SQLite uses `batch_alter_table`,
which rebuilds and copies the table because SQLite cannot alter a column
type at all. It also checks the live schema before each step, so it is safe
to run against a database that is already correct.

**On boot the app now logs whether the schema matches the code** rather than
guessing:

```
SCHEMA: up to date (revision b20d0000a001).
SCHEMA MISMATCH: database is at revision X but the code expects Y. Run `flask db upgrade`.
```

### Both upgrade paths were tested

| Scenario | Result |
|---|---|
| Fresh empty database → `flask db upgrade` | 63 tables, all columns correct |
| Legacy Float database (built the old way, seeded with awkward amounts) → `stamp` + `upgrade` | All 28 columns converted, all rows preserved, debit/credit sums still equal |

---

## 6. A test suite exists

Previously: 10,900 lines of code, an accounting engine that must balance,
zero tests.

**26 passing, 1 skipped** (the PostgreSQL-only exactness check).

Each test builds its database by running the **real Alembic migrations**,
not `create_all()`. If a migration is broken the tests fail — which is the
point.

```
tests/test_security.py          SECRET_KEY, CSRF, login throttling
tests/test_money.py             float drift, ROUND_HALF_UP, 1,000-entry
                                trial balance, reversal to zero, balance
                                validation still enforced
tests/test_forms_still_work.py  real form POSTs with CSRF on; static sweep
                                for untokenised forms; AST check that no
                                create_all() has crept back in
```

Run them:

```
pip install pytest
FLASK_ENV=development SECRET_KEY=$(python -c "import secrets;print(secrets.token_hex(32))") pytest -q
```

The `create_all` check is AST-based rather than a grep, so the several
comments explaining why it was removed do not trip it — only a real call does.

---

## Files changed

**New**

```
app/types.py                    Money / Quantity / Rate column types
app/security.py                 SECRET_KEY validation, CSRF, login throttle
preflight_check_20d.py          pre-deployment check (read-only)
migrations/                     Alembic environment + 2 migrations
tests/                          conftest + 3 test modules
```

**Modified**

```
app/__init__.py                 SECRET_KEY guard, CSRF init, Migrate init,
                                secure-cookie default, schema drift warning
app/models.py                   29 columns retyped, LoginAttempt added
app/db_utils.py                 warn_if_migrations_pending()
app/routes/auth_routes.py       throttling
app/routes/admin_routes.py      backup creation is POST-only
9 route files                   db.create_all() removed
69 templates                    87 CSRF tokens added
requirements.txt                +Flask-WTF, +Flask-Migrate, +alembic
.env.example                    new variables documented
deployment_render.md            Phase 20D deployment procedure
```

---

## Not fixed in this release

**Uploads and backups are still on Render's ephemeral local disk.** Every
deploy can delete uploaded payment proofs, invoices and documents — and the
backup system writes to that same disappearing disk. This is the largest
remaining risk and it is a data-loss risk, not a theoretical one.

**Before anything else: open production and try to download an attachment
from a payment request made a few weeks ago.** If it 404s, data has already
been lost, and moving to object storage becomes the immediate next job
rather than the next scheduled one.

Also still open, from the Phase 20C review and unchanged here: no
purchasing/supplier module, no stock-on-hand, no sales invoice or AR, only
two auto-journals (so the ledger still cannot show gross profit), no cash
flow statement or aging reports, no fiscal period lock, and no Retained
Earnings account.
