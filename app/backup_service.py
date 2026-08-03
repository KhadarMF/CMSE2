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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from flask import current_app
from flask_login import current_user
from sqlalchemy import inspect, text, Boolean, DateTime, Date, Integer

from app import db
from app.db_utils import sync_postgres_sequences

BACKUP_VERSION = "18A.4"

RESTORE_LOCK_FILENAME = "RESTORE_IN_PROGRESS.json"
RESTORE_LOG_DIR_NAME = "restore_logs"


def _now_stamp() -> str:
    # Microsecond precision matters: two backups created within the same
    # second (e.g. a manual backup immediately followed by the automatic
    # pre-restore safety backup) must never collide on filename. A previous
    # second-resolution stamp caused a real, confirmed bug where the
    # pre-restore backup silently overwrote the very backup being restored
    # from. create_backup() also has its own defensive uniqueness check
    # below in case this is ever called twice in the same microsecond.
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


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


def create_backup(label: str = "Manual") -> Dict[str, Any]:
    health = health_check()
    backup_root = get_backup_root()
    stamp = _now_stamp()
    filename = f"CMSE_Backup_{stamp}.zip"
    final_zip = backup_root / filename
    # Defense in depth on top of the microsecond timestamp: never write over
    # an existing backup file. A prior second-resolution timestamp let the
    # automatic pre-restore safety backup silently overwrite the backup a
    # restore was reading from, mid-restore. That was a confirmed, real bug,
    # not a hypothetical one — this guard is here because of it.
    collision_suffix = 2
    while final_zip.exists():
        filename = f"CMSE_Backup_{stamp}_{collision_suffix}.zip"
        final_zip = backup_root / filename
        collision_suffix += 1

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
            "label": label,
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
    """Backward-compatible backup listing; now returns rich 18A.3 metadata."""
    return list_backups_rich()


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


# -----------------------------
# Phase 18A.3 Enterprise Backup Manager helpers
# -----------------------------
def _read_zip_json(path: Path, member: str) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if member not in zf.namelist():
                return {}
            with zf.open(member) as f:
                return json.loads(f.read().decode("utf-8"))
    except Exception:
        return {}


def inspect_backup_file(path: Path) -> Dict[str, Any]:
    """Return rich metadata for a single backup zip without restoring anything."""
    stat = path.stat()
    manifest = _read_zip_json(path, "manifest.json")
    info = _read_zip_json(path, "backup_info.json")

    ok, message = verify_backup(path.name)
    database_kind = manifest.get("database_kind") or "Unknown"
    created_by = manifest.get("created_by") or "Unknown"
    created_at = info.get("created_at") or manifest.get("created_at") or datetime.fromtimestamp(stat.st_mtime).isoformat()

    pg_dump = manifest.get("pg_dump", {}) if isinstance(manifest.get("pg_dump"), dict) else {}
    json_export = manifest.get("json_export", {}) if isinstance(manifest.get("json_export"), dict) else {}
    files = manifest.get("files", {}) if isinstance(manifest.get("files"), dict) else {}

    status = "Healthy" if ok else "Warning"
    label = manifest.get("label") or "Manual"
    table_count = json_export.get("tables", "-")
    file_count = files.get("file_count", "-")

    return {
        "name": path.name,
        "size": _human_size(stat.st_size),
        "size_bytes": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "created_at_iso": created_at,
        "sha256": _sha256_file(path),
        "database_kind": database_kind,
        "created_by": created_by,
        "status": status,
        "verify_message": message,
        "label": label,
        "pg_dump_included": bool(pg_dump.get("included")),
        "table_count": table_count,
        "file_count": file_count,
        "backup_version": manifest.get("backup_version", "Unknown"),
        "has_manifest": bool(manifest),
        "has_backup_info": bool(info),
    }


def list_backups_rich(filters: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
    filters = filters or {}
    root = get_backup_root()
    query = (filters.get("q") or "").strip().lower()
    status_filter = (filters.get("status") or "").strip().lower()
    label_filter = (filters.get("label") or "").strip().lower()

    items: List[Dict[str, Any]] = []
    for p in sorted(root.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            item = inspect_backup_file(p)
        except OSError:
            continue
        haystack = " ".join([
            item.get("name", ""), item.get("created_by", ""), item.get("database_kind", ""),
            item.get("status", ""), item.get("label", ""), item.get("backup_version", ""),
        ]).lower()
        if query and query not in haystack:
            continue
        if status_filter and item.get("status", "").lower() != status_filter:
            continue
        if label_filter and item.get("label", "").lower() != label_filter:
            continue
        items.append(item)
    return items


def backup_statistics(backups: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    if backups is None:
        backups = list_backups_rich()
    total = len(backups)
    total_bytes = sum(int(b.get("size_bytes") or 0) for b in backups)
    largest = max(backups, key=lambda b: int(b.get("size_bytes") or 0), default=None)
    latest = backups[0] if backups else None
    healthy_count = sum(1 for b in backups if b.get("status") == "Healthy")
    warning_count = total - healthy_count
    avg = int(total_bytes / total) if total else 0
    return {
        "total_backups": total,
        "total_storage": _human_size(total_bytes),
        "average_size": _human_size(avg),
        "largest_backup": largest.get("name") if largest else "-",
        "largest_backup_size": largest.get("size") if largest else "-",
        "latest_backup": latest.get("name") if latest else "-",
        "latest_backup_date": latest.get("created_at") if latest else "-",
        "healthy_count": healthy_count,
        "warning_count": warning_count,
    }


def database_size_human() -> str:
    try:
        kind = get_database_kind()
        if kind == "PostgreSQL":
            size = db.session.execute(text("SELECT pg_database_size(current_database())")).scalar()
            return _human_size(int(size or 0))
        if kind == "SQLite":
            uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
            db_path = uri.replace("sqlite:///", "", 1)
            if not os.path.isabs(db_path):
                db_path = str(Path(current_app.instance_path) / db_path)
            p = Path(db_path)
            return _human_size(p.stat().st_size) if p.exists() else "Unknown"
    except Exception:
        pass
    return "Unknown"


def enterprise_health_summary(backups: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    backups = backups if backups is not None else list_backups_rich()
    health = health_check()
    stats = backup_statistics(backups)
    health["database_size"] = database_size_human()
    health["backup_folder_size"] = stats["total_storage"]
    health["last_backup"] = stats["latest_backup_date"]
    if not backups:
        health["backup_status"] = "Warning"
        health["backup_status_detail"] = "No backup has been created yet."
    elif stats["warning_count"]:
        health["backup_status"] = "Warning"
        health["backup_status_detail"] = f"{stats['warning_count']} backup(s) need attention."
    else:
        health["backup_status"] = "Healthy"
        health["backup_status_detail"] = "All listed backups passed verification."
    return health


# -----------------------------
# Phase 18A.4 Restore Engine
# -----------------------------
#
# Design notes (read before changing this section):
#
# 1. The restore log lives on disk (restore_logs/*.json), never in the
#    database. If a restore replaces table data, any log row written to a
#    DB table would either be wiped by the DELETE pass or overwritten by
#    whatever the backup contained. A file-based log is the only way to
#    guarantee a restore attempt is still visible after it runs, including
#    failed attempts.
#
# 2. "json_data" mode is the default and the only mode that is guaranteed
#    to exist for every backup, and the only one that works across engines
#    (e.g. a backup taken on SQLite restored into a Render PostgreSQL
#    database). It deletes and re-inserts rows table-by-table inside a
#    single transaction, so a failure partway through rolls back cleanly
#    and leaves the live database untouched.
#
# 3. "sqlite_file" and "postgres_sql" are exact/binary restores. They are
#    faster and byte-for-byte accurate, but sqlite_file replaces the whole
#    database file (no partial rollback) and postgres_sql drops and
#    recreates the entire schema before loading the dump. Both are opt-in
#    and postgres_sql additionally requires an explicit checkbox because
#    it can desync the live schema from the app's current models if the
#    dump predates a later migration.
#
# 4. A restore always writes an automatic "Before Restore" backup first,
#    using the same create_backup() used everywhere else, so a bad restore
#    can itself be restored.
#
# 5. RESTORE_IN_PROGRESS.json under the backup root is both a concurrency
#    lock (perform_restore refuses to start a second restore while one is
#    running) and the signal app/__init__.py checks to put the whole app
#    into maintenance mode for every other request while a restore runs.
#    This only works within a single filesystem/process. It does not
#    coordinate across multiple horizontally-scaled instances — if this
#    app is ever run as more than one Render instance at once, this lock
#    is not sufficient by itself and a shared lock (e.g. a DB row read
#    before the transaction that clears tables) would be needed instead.


def _zip_namelist(path: Path) -> List[str]:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            return zf.namelist()
    except Exception:
        return []


def _live_table_counts() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    try:
        with db.engine.connect() as conn:
            for table in db.metadata.sorted_tables:
                try:
                    counts[table.name] = conn.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar() or 0
                except Exception:
                    counts[table.name] = 0
    except Exception:
        pass
    return counts


def _restore_lock_path() -> Path:
    return get_backup_root() / RESTORE_LOCK_FILENAME


def is_restore_in_progress() -> bool:
    return _restore_lock_path().exists()


def get_restore_lock_info() -> Dict[str, Any] | None:
    path = _restore_lock_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"note": "A restore is in progress."}


def _acquire_restore_lock(info: Dict[str, Any]) -> None:
    _restore_lock_path().write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")


def _release_restore_lock() -> None:
    _restore_lock_path().unlink(missing_ok=True)


def _restore_log_dir() -> Path:
    d = get_backup_root() / RESTORE_LOG_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_restore_log(entry: Dict[str, Any]) -> str:
    log_id = entry.get("id") or f"RESTORE_{_now_stamp()}"
    entry["id"] = log_id
    path = _restore_log_dir() / f"{log_id}.json"
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return log_id


def list_restore_logs(limit: int = 200) -> List[Dict[str, Any]]:
    d = _restore_log_dir()
    items: List[Dict[str, Any]] = []
    for p in sorted(d.glob("RESTORE_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return items


def get_restore_log(log_id: str) -> Dict[str, Any] | None:
    if "/" in log_id or "\\" in log_id or not log_id.startswith("RESTORE_"):
        return None
    path = _restore_log_dir() / f"{log_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _actor_label() -> str:
    try:
        if current_user and current_user.is_authenticated:
            return getattr(current_user, "email", None) or getattr(current_user, "full_name", None) or f"user:{current_user.id}"
    except Exception:
        pass
    return "System"


def restore_preview(filename: str) -> Dict[str, Any]:
    """Everything the confirmation screen needs: verification, table diff,
    available restore modes and plain-language warnings. Never mutates
    anything."""
    root = get_backup_root()
    path = root / filename
    result: Dict[str, Any] = {"filename": filename, "name": filename, "exists": False}

    if "/" in filename or "\\" in filename or not filename.endswith(".zip"):
        result["error"] = "Invalid backup filename."
        return result
    if not path.exists():
        result["error"] = "Backup file not found."
        return result
    result["exists"] = True

    ok, message = verify_backup(filename)
    result["verified"] = ok
    result["verify_message"] = message

    detail = inspect_backup_file(path)
    result.update(detail)

    manifest = _read_zip_json(path, "manifest.json")
    backup_db_kind = manifest.get("database_kind") or "Unknown"
    live_kind = get_database_kind()
    result["backup_database_kind"] = backup_db_kind
    result["live_database_kind"] = live_kind
    result["engine_mismatch"] = bool(backup_db_kind) and backup_db_kind not in ("Unknown", live_kind)

    db_json = _read_zip_json(path, "database/database.json")
    backup_tables = db_json.get("tables", {}) if isinstance(db_json, dict) else {}
    live_counts = _live_table_counts()

    table_diff = []
    for name in sorted(set(backup_tables.keys()) | set(live_counts.keys())):
        backup_count = int(backup_tables.get(name, {}).get("row_count", 0)) if name in backup_tables else 0
        live_count = int(live_counts.get(name, 0))
        table_diff.append({"table": name, "backup_rows": backup_count, "live_rows": live_count, "delta": backup_count - live_count})
    result["table_diff"] = table_diff
    result["backup_total_rows"] = sum(t["backup_rows"] for t in table_diff)
    result["live_total_rows"] = sum(t["live_rows"] for t in table_diff)

    names = _zip_namelist(path)
    has_sql = "database/database.sql" in names
    has_sqlite = "database/database.sqlite3" in names
    has_json = "database/database.json" in names
    psql_available = shutil.which("psql") is not None

    modes = [
        {
            "id": "json_data",
            "label": "Data restore (recommended)",
            "available": has_json,
            "description": "Replaces all table data using the JSON export, inside one transaction. Keeps your current database schema. Works for PostgreSQL and SQLite, and across engines.",
        },
        {
            "id": "sqlite_file",
            "label": "SQLite file restore",
            "available": has_sqlite and live_kind == "SQLite",
            "description": "Replaces the live SQLite file with the one inside the backup. Exact binary restore, SQLite only, not transactional.",
        },
        {
            "id": "postgres_sql",
            "label": "PostgreSQL full SQL restore",
            "available": has_sql and live_kind == "PostgreSQL" and psql_available,
            "description": "Drops and recreates the entire schema from the pg_dump file, then loads data. Fast and exact, but if the app's models have changed since this backup, the restored schema will not match the running code until you re-run create_tables.py or a migration. Most destructive option.",
        },
    ]
    result["modes"] = modes

    age_days = None
    try:
        created_at_iso = detail.get("created_at_iso")
        if created_at_iso:
            created_dt = datetime.fromisoformat(str(created_at_iso).replace("Z", "+00:00"))
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - created_dt).days
    except Exception:
        pass
    result["age_days"] = age_days

    warnings: List[str] = []
    if not ok:
        warnings.append(f"This backup failed verification and cannot be restored: {message}")
    if result["engine_mismatch"]:
        warnings.append(f"This backup was taken on {backup_db_kind}, the live database is {live_kind}. Only Data restore will work.")
    if age_days is not None and age_days > 30:
        warnings.append(f"This backup is {age_days} days old. Anything created or changed since then will be lost from restored tables.")
    if is_restore_in_progress():
        warnings.append("A restore is already in progress. Wait for it to finish before starting another.")
    result["warnings"] = warnings
    result["can_restore"] = ok and not is_restore_in_progress()

    return result


def _coerce_value_for_column(value: Any, column: Any) -> Any:
    if value is None or column is None:
        return value
    col_type = column.type
    try:
        if isinstance(col_type, DateTime) and isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(col_type, Date) and not isinstance(col_type, DateTime) and isinstance(value, str):
            return date.fromisoformat(value[:10])
        if isinstance(col_type, Boolean):
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "t", "yes")
        if isinstance(col_type, Integer) and isinstance(value, str) and value.strip() != "":
            try:
                return int(value)
            except ValueError:
                return value
    except Exception:
        return value
    return value


def _restore_tables_from_json(export: Dict[str, Any]) -> Dict[str, Any]:
    """Replace all table data with rows from a database.json export.

    Deletes existing rows children-first, then inserts backup rows
    parents-first, inside a single transaction on a dedicated connection.
    On any error the transaction is rolled back so the live database is
    left exactly as it was before the call.
    """
    tables_data = export.get("tables", {}) if isinstance(export, dict) else {}
    sorted_tables = list(db.metadata.sorted_tables)
    restored_counts: Dict[str, int] = {}
    skipped_tables: List[str] = []

    connection = db.engine.connect()
    trans = connection.begin()
    try:
        for table in reversed(sorted_tables):
            connection.execute(table.delete())

        for table in sorted_tables:
            table_export = tables_data.get(table.name)
            if not table_export:
                skipped_tables.append(table.name)
                continue
            rows = table_export.get("rows", [])
            if not rows:
                restored_counts[table.name] = 0
                continue
            column_map = {c.name: c for c in table.columns}
            prepared_rows = []
            for row in rows:
                prepared = {}
                for key, value in row.items():
                    column = column_map.get(key)
                    if column is None:
                        continue
                    prepared[key] = _coerce_value_for_column(value, column)
                prepared_rows.append(prepared)
            connection.execute(table.insert(), prepared_rows)
            restored_counts[table.name] = len(prepared_rows)

        trans.commit()
    except Exception:
        trans.rollback()
        raise
    finally:
        connection.close()

    return {"restored_counts": restored_counts, "skipped_tables": skipped_tables}


def perform_restore(
    filename: str,
    mode: str = "json_data",
    restore_files: bool = True,
    full_schema_confirmed: bool = False,
) -> Dict[str, Any]:
    if is_restore_in_progress():
        raise RuntimeError("A restore is already in progress. Wait for it to finish before starting another one.")

    root = get_backup_root()
    path = root / filename
    if "/" in filename or "\\" in filename or not filename.endswith(".zip"):
        raise ValueError("Invalid backup filename.")
    if not path.exists():
        raise ValueError("Backup file not found.")

    ok, verify_message = verify_backup(filename)
    if not ok:
        raise ValueError(f"Backup failed verification and cannot be restored: {verify_message}")

    if mode not in ("json_data", "sqlite_file", "postgres_sql"):
        raise ValueError(f"Unknown restore mode: {mode}")
    if mode == "postgres_sql" and not full_schema_confirmed:
        raise ValueError("PostgreSQL full SQL restore requires the explicit schema-replace checkbox to be checked.")

    actor = _actor_label()
    started_at = _now_iso()
    log_id = f"RESTORE_{_now_stamp()}"
    _acquire_restore_lock({
        "id": log_id, "filename": filename, "mode": mode,
        "started_at": started_at, "started_by": actor, "status": "running",
    })

    log_entry: Dict[str, Any] = {
        "id": log_id, "source_backup": filename, "mode": mode, "restore_files": restore_files,
        "started_at": started_at, "started_by": actor, "status": "running",
        "pre_restore_backup": None, "table_counts": {}, "skipped_tables": [],
        "files_restored": 0, "error": None, "finished_at": None, "duration_seconds": None,
    }
    start = datetime.now(timezone.utc)

    try:
        pre_backup = create_backup(label="Before Restore")
        log_entry["pre_restore_backup"] = pre_backup["filename"]

        with tempfile.TemporaryDirectory(prefix="cmse_restore_") as tmp:
            tmp_path = Path(tmp)
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(tmp_path)

            if mode == "json_data":
                db_json_path = tmp_path / "database" / "database.json"
                if not db_json_path.exists():
                    raise ValueError("This backup does not contain a database.json export; Data restore is unavailable for it.")
                export = json.loads(db_json_path.read_text(encoding="utf-8"))
                outcome = _restore_tables_from_json(export)
                log_entry["table_counts"] = outcome["restored_counts"]
                log_entry["skipped_tables"] = outcome["skipped_tables"]
                db.session.remove()
                try:
                    sync_postgres_sequences()
                except Exception:
                    pass

            elif mode == "sqlite_file":
                if get_database_kind() != "SQLite":
                    raise ValueError("SQLite file restore is only available when the live database is SQLite.")
                sqlite_backup = tmp_path / "database" / "database.sqlite3"
                if not sqlite_backup.exists():
                    raise ValueError("This backup does not contain a SQLite database file.")
                uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
                db_path = uri.replace("sqlite:///", "", 1)
                if not os.path.isabs(db_path):
                    db_path = str(Path(current_app.instance_path) / db_path)
                target = Path(db_path)
                db.session.remove()
                db.engine.dispose()
                # Copy to a temp file next to the target, verify it, then swap it in
                # with an atomic rename rather than overwriting the live file's
                # content in place. This avoids any window where a reader could see
                # a partially-written file.
                tmp_target = target.with_name(target.name + f".restoring_{_now_stamp()}")
                shutil.copy2(sqlite_backup, tmp_target)
                if _sha256_file(tmp_target) != _sha256_file(sqlite_backup):
                    tmp_target.unlink(missing_ok=True)
                    raise RuntimeError(
                        "SQLite file restore did not verify: the copied file does not match "
                        "the backup. No data was changed; the automatic safety backup taken "
                        "before this restore is unaffected."
                    )
                os.replace(tmp_target, target)
                for stale in (Path(str(target) + "-wal"), Path(str(target) + "-shm"), Path(str(target) + "-journal")):
                    stale.unlink(missing_ok=True)
                log_entry["table_counts"] = {"_note": "SQLite file replaced whole; per-table counts are not tracked for this mode."}

            elif mode == "postgres_sql":
                if get_database_kind() != "PostgreSQL":
                    raise ValueError("PostgreSQL SQL restore is only available when the live database is PostgreSQL.")
                sql_backup = tmp_path / "database" / "database.sql"
                if not sql_backup.exists():
                    raise ValueError("This backup does not contain a pg_dump SQL file.")
                if shutil.which("psql") is None:
                    raise ValueError("psql is not installed on this server; PostgreSQL SQL restore is unavailable.")
                uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
                db.session.remove()
                db.engine.dispose()
                drop_proc = subprocess.run(
                    ["psql", uri, "-v", "ON_ERROR_STOP=1", "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"],
                    capture_output=True, timeout=120,
                )
                if drop_proc.returncode != 0:
                    raise ValueError(f"Failed to reset schema before restore: {drop_proc.stderr.decode('utf-8', errors='ignore')}")
                restore_proc = subprocess.run(
                    ["psql", uri, "-v", "ON_ERROR_STOP=1", "-f", str(sql_backup)],
                    capture_output=True, timeout=600,
                )
                if restore_proc.returncode != 0:
                    raise ValueError(f"psql restore failed: {restore_proc.stderr.decode('utf-8', errors='ignore')[-2000:]}")
                log_entry["table_counts"] = {"_note": "Full SQL restore executed; schema and data replaced from pg_dump."}
                try:
                    sync_postgres_sequences()
                except Exception:
                    pass

            if restore_files:
                uploads_src = tmp_path / "files" / "uploads"
                if uploads_src.exists():
                    upload_folder = Path(current_app.config.get("UPLOAD_FOLDER", current_app.root_path + "/uploads"))
                    upload_folder.mkdir(parents=True, exist_ok=True)
                    copied = 0
                    for p in uploads_src.rglob("*"):
                        if p.is_file():
                            dest = upload_folder / p.relative_to(uploads_src)
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(p, dest)
                            copied += 1
                    log_entry["files_restored"] = copied

        log_entry["status"] = "completed"
    except Exception as exc:
        log_entry["status"] = "failed"
        log_entry["error"] = str(exc)
        raise
    finally:
        finished = datetime.now(timezone.utc)
        log_entry["finished_at"] = finished.isoformat()
        log_entry["duration_seconds"] = round((finished - start).total_seconds(), 2)
        _write_restore_log(log_entry)
        _release_restore_lock()

    return log_entry
