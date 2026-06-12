#!/usr/bin/env python
"""
Fairview School Portal — database backup utility
================================================
DB-agnostic, reads DATABASE_URL from settings. Produces a timestamped,
consistent snapshot and prunes old backups by retention.

Usage:
    python scripts/backup_db.py                 # backup, default 14-day retention
    BACKUP_DIR=/var/backups/fairview \\
    BACKUP_RETENTION_DAYS=30 python scripts/backup_db.py

Engines:
  • SQLite (dev): a consistent snapshot via `VACUUM INTO` (no locking copy).
  • MySQL / TiDB (prod): runs `mysqldump` if available, else prints the exact
    command to run from your DB host / CI job.
  • PostgreSQL: runs `pg_dump` if available, else prints the command.

This script is the *mechanism*. Schedule it (cron / systemd timer / CI nightly)
and ship the output off-box — see BACKUP.md for the full runbook.
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.config import get_settings  # noqa: E402


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _backup_dir() -> Path:
    d = Path(os.environ.get("BACKUP_DIR", "backups"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _prune(backup_dir: Path, prefix: str) -> None:
    days = int(os.environ.get("BACKUP_RETENTION_DAYS", "14"))
    if days <= 0:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for f in backup_dir.glob(f"{prefix}*"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            f.unlink(missing_ok=True)
            print(f"  pruned old backup: {f.name}")


def _backup_sqlite(url: str, backup_dir: Path) -> Path:
    import sqlite3

    # sqlite+aiosqlite:///./extracare.db  ->  ./extracare.db
    raw = url.split("///", 1)[-1].split("?", 1)[0]
    src_path = Path(raw)
    if not src_path.exists():
        raise SystemExit(f"SQLite database not found: {src_path}")

    dest = backup_dir / f"fairview-{_timestamp()}.db"
    # VACUUM INTO is online + transactionally consistent (no readers blocked).
    con = sqlite3.connect(str(src_path))
    try:
        con.execute("VACUUM INTO ?", (str(dest),))
    finally:
        con.close()

    # Compress to save space; keep the .db too short-lived -> gzip in place.
    gz = dest.with_suffix(dest.suffix + ".gz")
    with open(dest, "rb") as fi, gzip.open(gz, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    dest.unlink(missing_ok=True)
    return gz


def _backup_mysql(url: str, backup_dir: Path) -> Path | None:
    p = urlparse(url)
    user = unquote(p.username or "")
    password = unquote(p.password or "")
    host = p.hostname or "localhost"
    port = str(p.port or 3306)
    db = (p.path or "/").lstrip("/")
    dest = backup_dir / f"fairview-{_timestamp()}.sql.gz"

    cmd = [
        "mysqldump", "--single-transaction", "--quick", "--routines", "--triggers",
        "-h", host, "-P", port, "-u", user, db,
    ]
    printable = " ".join(cmd).replace(db, db)  # password passed via env, not argv
    if shutil.which("mysqldump") is None:
        print("mysqldump not found on PATH. Run this on your DB host / CI:")
        print(f"  MYSQL_PWD='***' {printable} | gzip > {dest}")
        return None

    env = {**os.environ, "MYSQL_PWD": password}
    with gzip.open(dest, "wb") as fo:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, env=env, check=True)
        fo.write(proc.stdout)
    return dest


def _backup_postgres(url: str, backup_dir: Path) -> Path | None:
    p = urlparse(url)
    dest = backup_dir / f"fairview-{_timestamp()}.dump"
    # asyncpg URL -> libpq-compatible URL
    libpq = url.replace("postgresql+asyncpg", "postgresql").replace("postgresql+psycopg", "postgresql")
    cmd = ["pg_dump", "--format=custom", "--no-owner", "--dbname", libpq, "--file", str(dest)]
    if shutil.which("pg_dump") is None:
        print("pg_dump not found on PATH. Run this on your DB host / CI:")
        print(f"  pg_dump --format=custom --no-owner '{libpq}' > {dest}")
        return None
    subprocess.run(cmd, check=True)
    return dest


def main() -> None:
    settings = get_settings()
    url = settings.DATABASE_URL
    backup_dir = _backup_dir()
    print(f"Backing up {settings.SCHOOL_NAME} ({settings.ENVIRONMENT}) ...")

    if url.startswith("sqlite"):
        out = _backup_sqlite(url, backup_dir)
    elif url.startswith("mysql"):
        out = _backup_mysql(url, backup_dir)
    elif url.startswith("postgres"):
        out = _backup_postgres(url, backup_dir)
    else:
        raise SystemExit(f"Unsupported DATABASE_URL scheme: {url.split(':',1)[0]}")

    if out is not None:
        size_mb = out.stat().st_size / 1_048_576
        print(f"✓ Backup written: {out}  ({size_mb:.2f} MB)")
        _prune(backup_dir, "fairview-")
    print("Done. Remember to copy this off-box (S3/GCS/another region).")


if __name__ == "__main__":
    main()
