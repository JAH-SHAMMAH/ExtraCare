#!/usr/bin/env python
"""Restore a logical backup into an EMPTY, already-migrated database.

  python scripts/restore_logical_backup.py <dump.jsonl.gz> <target-db-url>

Recovery procedure this completes:
  1. createdb <new>
  2. DATABASE_URL=<new> alembic upgrade <the revision recorded in the dump>
  3. this script

Step 2 matters: the dump is DATA ONLY. Alembic owns the schema, so the recorded
revision is what makes the data loadable — restoring into a schema built from a
different revision is the one way this goes quietly wrong, so the revision is
checked against the target's alembic_version before a single row is written.

Rows are inserted in the dump's recorded table order, which is FK-dependency
order, so parents land before children and no constraint has to be deferred.

SAFETY: refuses to write to a database whose name looks like production unless
--force is given. A restore is destructive to whatever is already there.
"""
from __future__ import annotations

import asyncio
import base64
import gzip
import json
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import MetaData, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

PRODUCTION_DB_NAMES = {"fairview_data"}
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
        raise SystemExit("Not a fairview logical dump (no header).")
    return meta, tables


async def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    path, target = Path(sys.argv[1]), sys.argv[2]
    force = "--force" in sys.argv

    db_name = target.rstrip("/").split("/")[-1].split("?")[0]
    if db_name in PRODUCTION_DB_NAMES and not force:
        raise SystemExit(
            f"REFUSING: '{db_name}' looks like the production database. A restore "
            f"overwrites what is there. Pass --force only if you truly mean it."
        )

    meta, tables = read_dump(path)
    print("=" * 78)
    print("RESTORE")
    print("=" * 78)
    print(f"dump             : {path.name}")
    print(f"taken from       : {meta.get('server_version')}")
    print(f"alembic_revision : {meta.get('alembic_revision')}")
    print(f"target database  : {db_name}")

    async_url = target.replace("postgresql://", "postgresql+asyncpg://").split("?")[0]
    engine = create_async_engine(async_url)
    written: dict[str, int] = {}
    try:
        async with engine.begin() as conn:
            have = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            want = meta.get("alembic_revision")
            if have != want:
                raise SystemExit(
                    f"REFUSING: target is at alembic revision {have!r} but the dump was "
                    f"taken at {want!r}. Run `alembic upgrade {want}` on the target first."
                )
            print(f"revision check   : target at {have} — matches the dump")

            md = MetaData()
            await conn.run_sync(md.reflect)
            by_name = {t.name: t for t in md.sorted_tables}

            order = meta.get("table_order") or list(tables)
            print(f"\nloading {sum(len(v) for v in tables.values()):,} rows "
                  f"across {len([t for t in order if tables.get(t)])} non-empty tables ...")
            for name in order:
                rows = tables.get(name) or []
                if not rows:
                    continue
                t = by_name.get(name)
                if t is None:
                    raise SystemExit(f"Target has no table {name!r} — schema mismatch.")
                payload = [{k: _decode(v) for k, v in r.items()} for r in rows]
                for i in range(0, len(payload), BATCH):
                    await conn.execute(t.insert(), payload[i:i + BATCH])
                written[name] = len(payload)
                print(f"    {name:<44} {len(payload):>7} rows", flush=True)
    finally:
        await engine.dispose()

    print(f"\n[OK] restored {sum(written.values()):,} rows into {len(written)} tables")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
