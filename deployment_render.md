# Deploy Phase 8 on Render

## 1. Upload project to GitHub

Do not upload:

- `.env`
- `env/`
- `instance/`
- `backups/`

## 2. Create PostgreSQL on Render

```text
New → PostgreSQL
```

Copy the database URL.

## 3. Create Web Service

```text
New → Web Service
```

Connect GitHub repository.

## 4. Build command

```bash
pip install -r requirements.txt
```

## 5. Start command

```bash
gunicorn wsgi:app
```

## 6. Environment variables

```text
SECRET_KEY=long-random-secret-key
DATABASE_URL=postgresql://...
FLASK_ENV=production
MAX_UPLOAD_MB=20
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_gmail_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com
```

## 7. Create database tables

Open Render Shell:

```bash
python init_db.py
```

## Important

For uploaded files, Render free local disk may not be permanent. Use persistent disk or cloud storage for production.

---

## Phase 20D deployment steps (READ BEFORE DEPLOYING)

This release changes three things that will stop the app from starting if
they are skipped. Follow the order.

### 1. Back up, and download the backup

Admin > Backup > Create Backup, then **Download** it to your own computer.
Render's disk is ephemeral, so a backup that stays on the server is not a
backup. The schema migration rewrites every money column in place; if it
goes wrong the downloaded file is the only way back.

### 2. Set SECRET_KEY in Render environment variables

Generate one:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste it into Render > Environment > `SECRET_KEY`.

**The app now refuses to boot in production without it.** That is
deliberate: the old fallback value was published in the source code, so
anyone could mint an Admin session cookie.

**Everyone will be logged out** when this changes. Tell staff the day before.

### 3. Run the pre-flight check

From a Render shell (or locally against the production `DATABASE_URL`):

```
python preflight_check_20d.py
```

It reports whether SECRET_KEY is acceptable, which stored values will be
rounded by the numeric conversion, and what the schema state is. It changes
nothing.

### 4. Migrate the database

The schema is now owned by Alembic. `db.create_all()` has been removed from
every route - it only ever created missing *tables* and silently ignored
missing *columns*, which is how the schema drifted.

For the **existing** production database (tables already exist):

```
flask db stamp cc82184d6822
flask db upgrade
```

For a **brand new empty** database:

```
flask db upgrade
```

From now on, after any model change:

```
flask db migrate -m "what changed"
flask db upgrade
```

Add this to the Render start command so migrations run on every deploy:

```
flask db upgrade && gunicorn wsgi:app
```

### 5. Verify

- Log in. If the login form 400s, the CSRF token is not rendering - check
  that the template extends `base.html`.
- Submit one form in each module you use daily (payment request, journal
  entry, quotation).
- Deliberately fail login 5 times and confirm you get the lockout message.
- Check the boot logs for `SCHEMA: up to date`.

### Still outstanding after 20D

Uploads and backups are still written to Render's ephemeral local disk.
**Payment proof images and uploaded documents are still at risk of being
deleted on every deploy.** Moving them to object storage (S3, Cloudflare R2)
is the next piece of work and is not included in this release.
