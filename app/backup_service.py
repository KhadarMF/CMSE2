"""Phase 18A.1 Backup Foundation for CMSE ERP.

This module intentionally does not implement restore. It creates a safe,
downloadable ZIP backup for PostgreSQL/Render and SQLite/local deployments.
It avoids changing authentication, permissions, sessions, or business logic.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from flask import current_app
from flask_login import current_user
from sqlalchemy import inspect, text

from app import db

BACKUP_VERSION = "18A.1"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_backup_root() -> Path:
    configured = os.environ.get("CMSE_BACKUP_DIR", "").strip()
    if configured:
        root = Path(configured)
    else:
        root = Path(current_app.root_path).parent / "backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_database_kind() -> str:
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    if uri.startswith("postgresql") or uri.startswith("postgres"):
        return "PostgreSQL"
    if uri.startswith("sqlite"):
        return "SQLite"
    return uri.split(":", 1)[0] or "Unknown"


def _safe_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime,)):
        return value.isoformat()
    # dates, decimals, UUIDs, bytes, etc.
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return value.hex()
    return str(value)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _human_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def health_check() -> Dict[str, Any]:
    backup_root = get_backup_root()
    upload_folder = Path(current_app.config.get("UPLOAD_FOLDER", current_app.root_path + "/uploads"))
    checks: List[Dict[str, str]] = []

    try:
        db.session.execute(text("SELECT 1"))
        checks.append({"name": "Database connection", "status": "OK", "detail": "Connected"})
    except Exception as exc:
        checks.append({"name": "Database connection", "status": "ERROR", "detail": str(exc)})

    try:
        backup_root.mkdir(parents=True, exist_ok=True)
        test_file = backup_root / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        checks.append({"name": "Backup folder", "status": "OK", "detail": str(backup_root)})
    except Exception as exc:
        checks.append({"name": "Backup folder", "status": "ERROR", "detail": str(exc)})

    if upload_folder.exists():
        checks.append({"name": "Upload folder", "status": "OK", "detail": str(upload_folder)})
    else:
        checks.append({"name": "Upload folder", "status": "WARNING", "detail": f"Not found: {upload_folder}"})

    try:
        usage = shutil.disk_usage(str(backup_root))
        checks.append({"name": "Disk free", "status": "OK", "detail": _human_size(usage.free)})
    except Exception as exc:
        checks.append({"name": "Disk free", "status": "WARNING", "detail": str(exc)})

    return {
        "database_kind": get_database_kind(),
        "backup_root": str(backup_root),
        "upload_folder": str(upload_folder),
        "upload_size": _human_size(_directory_size(upload_folder)),
        "checks": checks,
        "healthy": not any(c["status"] == "ERROR" for c in checks),
    }


def _try_pg_dump(output_sql: Path) -> Tuple[bool, str]:
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    if not uri.startswith("postgresql") and not uri.startswith("postgres"):
        return False, "Not PostgreSQL"
    if shutil.which("pg_dump") is None:
        return False, "pg_dump not installed; JSON table export included instead"

    # pg_dump accepts the SQLAlchemy URL when postgresql://.
    env = os.environ.copy()
    cmd = ["pg_dump", "--no-owner", "--no-privileges", "--format=plain", uri]
    try:
        with output_sql.open("wb") as f:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env, timeout=120)
        if proc.returncode == 0 and output_sql.exists() and output_sql.stat().st_size > 0:
            return True, "pg_dump completed"
        return False, proc.stderr.decode("utf-8", errors="ignore") or "pg_dump failed"
    except Exception as exc:
        return False, str(exc)


def _export_sqlite_file(target: Path) -> Tuple[bool, str]:
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    if not uri.startswith("sqlite"):
        return False, "Not SQLite"
    # sqlite:///relative.db or sqlite:////absolute.db
    db_path = uri.replace("sqlite:///", "", 1)
    if not os.path.isabs(db_path):
        db_path = str(Path(current_app.instance_path) / db_path)
    source = Path(db_path)
    if not source.exists():
        # common fallback for this project
        source = Path(current_app.instance_path) / "solar_documents.db"
    if source.exists():
        shutil.copy2(source, target)
        return True, f"SQLite database copied from {source}"
    return False, f"SQLite database file not found: {source}"


def _export_database_json(target: Path) -> Dict[str, Any]:
    inspector = inspect(db.engine)
    export: Dict[str, Any] = {
        "created_at": _now_iso(),
        "database_kind": get_database_kind(),
        "tables": {},
        "errors": [],
    }
    with db.engine.connect() as conn:
        for table in db.metadata.sorted_tables:
            table_name = table.name
            try:
                rows = conn.execute(table.select()).mappings().all()
                export["tables"][table_name] = {
                    "columns": [c.name for c in table.columns],
                    "row_count": len(rows),
                    "rows": [
                        {key: _safe_json_value(val) for key, val in dict(row).items()}
                        for row in rows
                    ],
                }
            except Exception as exc:
                export["errors"].append({"table": table_name, "error": str(exc)})
    target.write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")
    return export


def _write_table_csvs(folder: Path) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    count = 0
    with db.engine.connect() as conn:
        for table in db.metadata.sorted_tables:
            try:
                rows = conn.execute(table.select()).mappings().all()
                csv_path = folder / f"{table.name}.csv"
                with csv_path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=[c.name for c in table.columns])
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({key: _safe_json_value(val) for key, val in dict(row).items()})
                count += 1
            except Exception:
                continue
    return count


def create_backup() -> Dict[str, Any]:
    health = health_check()
    backup_root = get_backup_root()
    stamp = _now_stamp()
    filename = f"CMSE_Backup_{stamp}.zip"
    final_zip = backup_root / filename

    with tempfile.TemporaryDirectory(prefix="cmse_backup_") as tmp:
        tmp_path = Path(tmp)
        database_dir = tmp_path / "database"
        database_dir.mkdir()
        files_dir = tmp_path / "files"
        files_dir.mkdir()

        pg_dump_sql = database_dir / "database.sql"
        pg_dump_ok, pg_dump_message = _try_pg_dump(pg_dump_sql)
        if not pg_dump_ok and pg_dump_sql.exists():
            pg_dump_sql.unlink(missing_ok=True)

        sqlite_ok, sqlite_message = _export_sqlite_file(database_dir / "database.sqlite3")

        db_json = database_dir / "database.json"
        json_export = _export_database_json(db_json)
        csv_count = _write_table_csvs(database_dir / "tables_csv")

        upload_folder = Path(current_app.config.get("UPLOAD_FOLDER", current_app.root_path + "/uploads"))
        copied_files = 0
        if upload_folder.exists():
            dest_uploads = files_dir / "uploads"
            shutil.copytree(upload_folder, dest_uploads, dirs_exist_ok=True)
            copied_files = sum(1 for p in dest_uploads.rglob("*") if p.is_file())

        # Include lightweight system/config snapshot. Do not include secrets.
        safe_config = {
            "database_kind": get_database_kind(),
            "upload_folder": str(upload_folder),
            "max_content_length": current_app.config.get("MAX_CONTENT_LENGTH"),
            "session_cookie_name": current_app.config.get("SESSION_COOKIE_NAME"),
        }
        (tmp_path / "system.json").write_text(json.dumps(safe_config, indent=2), encoding="utf-8")

        user_label = "System"
        try:
            if current_user and current_user.is_authenticated:
                user_label = getattr(current_user, "email", None) or getattr(current_user, "full_name", None) or f"user:{current_user.id}"
        except Exception:
            pass

        manifest = {
            "backup_version": BACKUP_VERSION,
            "erp": "Cadceed-Maal Solar ERP",
            "created_at": _now_iso(),
            "created_by": user_label,
            "database_kind": get_database_kind(),
            "pg_dump": {"included": pg_dump_ok, "message": pg_dump_message},
            "sqlite_copy": {"included": sqlite_ok, "message": sqlite_message},
            "json_export": {"included": True, "tables": len(json_export.get("tables", {})), "errors": json_export.get("errors", [])},
            "csv_export": {"included": True, "tables": csv_count},
            "files": {"uploads_included": upload_folder.exists(), "file_count": copied_files},
            "health": health,
            "python": platform.python_version(),
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        with zipfile.ZipFile(final_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in tmp_path.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(tmp_path))

    size = final_zip.stat().st_size
    checksum = _sha256_file(final_zip)

    # Update manifest copy inside zip with final file info by adding backup_info.json.
    info = {
        "filename": filename,
        "size_bytes": size,
        "size_human": _human_size(size),
        "sha256": checksum,
        "created_at": _now_iso(),
    }
    with zipfile.ZipFile(final_zip, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("backup_info.json", json.dumps(info, indent=2))

    return {**info, "path": str(final_zip), "pg_dump_included": manifest["pg_dump"]["included"], "pg_dump_message": manifest["pg_dump"]["message"]}


def list_backups() -> List[Dict[str, Any]]:
    root = get_backup_root()
    items: List[Dict[str, Any]] = []
    for p in sorted(root.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            stat = p.stat()
            items.append({
                "name": p.name,
                "size": _human_size(stat.st_size),
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "sha256": _sha256_file(p),
            })
        except OSError:
            continue
    return items


def verify_backup(filename: str) -> Tuple[bool, str]:
    path = get_backup_root() / filename
    if not path.exists() or path.suffix.lower() != ".zip":
        return False, "Backup file not found"
    try:
        with zipfile.ZipFile(path, "r") as zf:
            bad = zf.testzip()
            if bad:
                return False, f"Corrupt file inside ZIP: {bad}"
            names = set(zf.namelist())
            required = {"manifest.json", "database/database.json", "backup_info.json"}
            missing = required - names
            if missing:
                return False, "Missing: " + ", ".join(sorted(missing))
        return True, "Backup verified successfully"
    except Exception as exc:
        return False, str(exc)
