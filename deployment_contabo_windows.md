# Deploy Phase 8 on Contabo Windows VPS

## 1. Install Python 3.10 or 3.11

## 2. Copy project to VPS

Example:

```text
C:\solar_doc_approval_phase8
```

## 3. Install requirements

```bash
cd C:\solar_doc_approval_phase8
python -m venv env
env\Scripts\activate
pip install -r requirements.txt
```

## 4. Create `.env`

Copy `.env.example` to `.env` and fill values.

For SQLite:

```text
DATABASE_URL=sqlite:///solar_documents.db
```

For PostgreSQL:

```text
DATABASE_URL=postgresql://username:password@localhost:5432/solar_doc_system
```

## 5. Initialize database

```bash
python init_db.py
```

## 6. Run production-style server

```bash
python serve_waitress.py
```

## 7. Open firewall

Allow TCP port 5000 in Windows Firewall.

## 8. Open system

```text
http://SERVER_IP:5000
```

For real production, add HTTPS with IIS/Nginx reverse proxy.
