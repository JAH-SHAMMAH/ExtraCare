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
import re
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


def _to_libpq(url: str) -> str:
    """SQLAlchemy/asyncpg URL -> one libpq will accept.

    Two things differ, and both are fatal to pg_dump rather than degrading:
    the driver suffix, and the TLS parameter — asyncpg spells it `ssl=require`
    (SQLAlchemy passes it through to the driver), libpq only knows `sslmode`.
    """
    libpq = url.replace("postgresql+asyncpg", "postgresql").replace("postgresql+psycopg", "postgresql")
    return re.sub(r"([?&])ssl=", r"\1sslmode=", libpq)


def _backup_postgres(url: str, backup_dir: Path) -> Path | None:
    dest = backup_dir / f"fairview-{_timestamp()}.dump"
    libpq = _to_libpq(url)
    if shutil.which("pg_dump") is not None:
        cmd = ["pg_dump", "--format=custom", "--no-owner", "--dbname", libpq, "--file", str(dest)]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            # pg_dump leaves a 0-byte file behind on failure; clear it so it can
            # never be mistaken for a backup by a retention sweep or an operator.
            dest.unlink(missing_ok=True)
            raise
        return dest

    # No pg_dump on this box. Previously that printed a hint and returned None —
    # and main() then exited 0 with nothing written, so a nightly cron reported
    # success forever while producing no backups. Fall back to a logical dump so
    # the data is always captured by SOME means, and say plainly which was used.
    print("pg_dump not found on PATH — falling back to a logical (data-only) dump.")
    print("  For a canonical schema+data dump, install the Postgres client tools and re-run:")
    print(f"  pg_dump --format=custom --no-owner '{libpq}' > {dest}")
    return _backup_postgres_logical(libpq, backup_dir)


# ── Logical fallback ──────────────────────────────────────────────────────────
# Data-only, engine-independent, and restorable via:
#     createdb <new> && alembic upgrade <recorded revision> && restore_logical_dump.py
# The schema comes from Alembic (the app owns it), so capturing DATA faithfully
# plus the exact migration revision is a complete recovery path. Rows are written
# in FK-dependency order so a restore can insert them straight through.

def _sql_str(v: str) -> str:
    """A single-quoted SQL literal — table names only, from schema reflection."""
    return "'" + v.replace("'", "''") + "'"


def _encode(v):
    """JSON-safe, loss-free encoding of a Postgres value."""
    import base64
    from datetime import date, datetime, time, timedelta
    from decimal import Decimal
    from uuid import UUID

    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (datetime, date, time)):
        return {"__t__": type(v).__name__, "v": v.isoformat()}
    if isinstance(v, timedelta):
        return {"__t__": "timedelta", "v": v.total_seconds()}
    if isinstance(v, Decimal):
        return {"__t__": "Decimal", "v": str(v)}
    if isinstance(v, UUID):
        return {"__t__": "UUID", "v": str(v)}
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"__t__": "bytes", "v": base64.b64encode(bytes(v)).decode()}
    if isinstance(v, (list, tuple)):
        return [_encode(x) for x in v]
    if isinstance(v, dict):
        return {k: _encode(x) for k, x in v.items()}
    return {"__t__": "repr", "v": str(v)}


async def _dump_logical(libpq_url: str, dest: Path) -> dict:
    import json

    from sqlalchemy import MetaData, select, text
    from sqlalchemy.ext.asyncio import create_async_engine

    async_url = libpq_url.replace("postgresql://", "postgresql+asyncpg://").split("?")[0]
    engine = create_async_engine(async_url, connect_args={"ssl": "require"}, pool_pre_ping=True)
    counts: dict[str, int] = {}
    try:
        async with engine.connect() as conn:
            meta = MetaData()
            await conn.run_sync(meta.reflect)
            server_version = (await conn.execute(text("SHOW server_version"))).scalar()
            try:
                revision = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            except Exception:  # noqa: BLE001
                revision = None

            # sorted_tables is FK-dependency order — parents before children, so a
            # restore can insert straight through without deferring constraints.
            tables = list(meta.sorted_tables)

            with gzip.open(dest, "wt", encoding="utf-8") as fo:
                fo.write(json.dumps({
                    "_meta": {
                        "format": "fairview-logical-v1",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "server_version": server_version,
                        "alembic_revision": revision,
                        "restore": ("create an empty database, `alembic upgrade "
                                    f"{revision}`, then load this file in table order"),
                        "table_order": [t.name for t in tables],
                    }
                }) + "\n")

                # Round trips, not row volume, are the cost here: this schema has
                # ~270 tables but only a few thousand rows, and a remote database
                # charges full latency for `SELECT * FROM empty_table`. One
                # UNION ALL gets every count in a single trip, so only the tables
                # that actually hold data are then fetched.
                count_sql = " UNION ALL ".join(
                    f'SELECT {_sql_str(t.name)} AS t, COUNT(*) AS n FROM "{t.name}"'
                    for t in tables
                )
                live_counts = {
                    r[0]: r[1] for r in (await conn.execute(text(count_sql))).all()
                }
                nonempty = [t for t in tables if live_counts.get(t.name, 0)]
                print(f"    {len(tables)} tables, {len(nonempty)} non-empty, "
                      f"{sum(live_counts.values())} rows", flush=True)

                for t in tables:
                    fo.write(json.dumps({"_table": t.name}) + "\n")
                    if not live_counts.get(t.name, 0):
                        counts[t.name] = 0
                        continue
                    rows = (await conn.execute(select(t))).mappings().all()
                    for row in rows:
                        fo.write(json.dumps({k: _encode(v) for k, v in row.items()}) + "\n")
                    counts[t.name] = len(rows)
                    print(f"    {t.name:<44} {len(rows):>7} rows", flush=True)
                fo.write(json.dumps({"_end": True, "counts": counts}) + "\n")
    finally:
        await engine.dispose()
    return counts


def _backup_postgres_logical(libpq_url: str, backup_dir: Path) -> Path:
    import asyncio

    dest = backup_dir / f"fairview-{_timestamp()}.logical.jsonl.gz"
    counts = asyncio.run(_dump_logical(libpq_url, dest))
    print(f"  logical dump: {len(counts)} tables, {sum(counts.values())} rows total")
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

    # A run that produced no file is a FAILURE, not a "Done." Exiting 0 here is
    # how a nightly cron reports success while backing up nothing — the runbook's
    # "alert if a nightly backup is missing or 0 bytes" can never fire if the job
    # itself never signals failure.
    if out is None:
        raise SystemExit("FAILED: no backup file was produced. See the message above.")
    size = out.stat().st_size
    if size == 0:
        out.unlink(missing_ok=True)
        raise SystemExit(f"FAILED: backup file was empty (removed): {out}")
    # ASCII only: the Windows console is cp1252 and a check mark raises
    # UnicodeEncodeError *after* the backup is safely on disk — turning a
    # successful run into a non-zero exit, which is the opposite of the
    # signal this script exists to give.
    print(f"[OK] Backup written: {out}  ({size / 1_048_576:.2f} MB)")
    _prune(backup_dir, "fairview-")
    print("Done. Remember to copy this off-box (S3/GCS/another region).")


if __name__ == "__main__":
    main()
