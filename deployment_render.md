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
