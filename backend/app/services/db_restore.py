"""Load a fairview-logical-v1 backup into the CURRENT (empty, migrated) database.

Same format and loading rules as scripts/restore_logical_backup.py, but runs
inside the app so a hosted database can be restored without a shell.
"""
from __future__ import annotations

import base64
import gzip
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import MetaData, text

SKIP_TABLES = {"alembic_version"}
BATCH = 500


def _decode(v):
    if isinstance(v, dict) and "__t__" in v:
        t, raw = v["__t__"], v["v"]
        if t == "datetime":
            return datetime.fromisoformat(raw)
        if t == "date":
            return date.fromisoformat(raw)
        if t == "time":
            return time.fromisoformat(raw)
        if t == "timedelta":
            return timedelta(seconds=raw)
        if t == "Decimal":
            return Decimal(raw)
        if t == "UUID":
            return UUID(raw)
        if t == "bytes":
            return base64.b64decode(raw)
        return raw
    if isinstance(v, list):
        return [_decode(x) for x in v]
    if isinstance(v, dict):
        return {k: _decode(x) for k, x in v.items()}
    return v


def read_dump(path: Path):
    meta = None
    tables: dict[str, list[dict]] = {}
    current = None
    with gzip.open(path, "rt", encoding="utf-8") as fi:
        for line in fi:
            obj = json.loads(line)
            if "_meta" in obj:
                meta = obj["_meta"]
            elif "_table" in obj:
                current = obj["_table"]
                tables.setdefault(current, [])
            elif "_end" in obj:
                break
            else:
                tables[current].append(obj)
    if meta is None:
        raise ValueError("Not a fairview logical dump (no header).")
    return meta, tables


async def restore_into(engine, path: Path) -> dict[str, int]:
    """One transaction: all rows land or none do. Refuses a non-empty database."""
    meta, tables = read_dump(path)
    written: dict[str, int] = {}
    async with engine.begin() as conn:
        users = (await conn.execute(text("SELECT count(*) FROM users"))).scalar()
        if users:
            raise RuntimeError("This database already has users; a restore only runs on an empty one.")
        md = MetaData()
        await conn.run_sync(md.reflect)
        by_name = {t.name: t for t in md.sorted_tables}
        for name in meta.get("table_order") or list(tables):
            rows = tables.get(name) or []
            if name in SKIP_TABLES or not rows:
                continue
            t = by_name.get(name)
            if t is None:
                raise RuntimeError(f"Target has no table {name!r} — schema mismatch.")
            payload = [{k: _decode(v) for k, v in r.items()} for r in rows]
            for i in range(0, len(payload), BATCH):
                await conn.execute(t.insert(), payload[i:i + BATCH])
            written[name] = len(payload)
    return written
