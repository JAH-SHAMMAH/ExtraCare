"""Whole-database backup, produced from the app's own database connection.

Same file format as ``scripts/backup_db.py``'s logical dump
(``fairview-logical-v1``: gzip JSON-lines, data only + the Alembic revision), so
``scripts/restore_logical_backup.py`` and ``verify_logical_backup.py`` read it
unchanged. It exists because the hosting plan offers no backup/export of its own.
"""
from __future__ import annotations

import base64
import gzip
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import MetaData, select, text
from sqlalchemy.ext.asyncio import AsyncEngine


def _encode(v):
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


async def dump_database(engine: AsyncEngine, dest: Path) -> dict[str, int]:
    """Write every table to ``dest`` (gzip JSON-lines). Returns rows per table."""
    counts: dict[str, int] = {}
    async with engine.connect() as conn:
        meta = MetaData()
        await conn.run_sync(meta.reflect)
        try:
            server_version = (await conn.execute(text("SHOW server_version"))).scalar()
        except Exception:  # noqa: BLE001 - non-Postgres (tests)
            server_version = engine.dialect.name
            await conn.rollback()
        try:
            revision = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        except Exception:  # noqa: BLE001
            revision = None
            await conn.rollback()

        tables = list(meta.sorted_tables)
        with gzip.open(dest, "wt", encoding="utf-8") as fo:
            fo.write(json.dumps({"_meta": {
                "format": "fairview-logical-v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "server_version": server_version,
                "alembic_revision": revision,
                "restore": ("create an empty database, `alembic upgrade "
                            f"{revision}`, then load this file in table order"),
                "table_order": [t.name for t in tables],
            }}) + "\n")
            for t in tables:
                fo.write(json.dumps({"_table": t.name}) + "\n")
                rows = (await conn.execute(select(t))).mappings().all()
                for row in rows:
                    fo.write(json.dumps({k: _encode(v) for k, v in row.items()}) + "\n")
                counts[t.name] = len(rows)
            fo.write(json.dumps({"_end": True, "counts": counts}) + "\n")
    return counts
