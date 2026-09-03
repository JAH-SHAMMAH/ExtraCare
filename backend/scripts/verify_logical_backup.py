#!/usr/bin/env python
"""Verify a logical backup against the database it came from.

  python scripts/verify_logical_backup.py <dump.jsonl.gz> [db-url]

"The script ran without error" is not evidence a backup is any good. This checks
the three things that actually matter, against the LIVE source:

  1. READABLE   — the gzip opens, every line parses, the header and footer are
                  present (so a truncated file is caught, not mistaken for a
                  short one).
  2. COMPLETE   — every table in the database appears, and each row count matches
                  the source exactly.
  3. FAITHFUL   — a random sample of rows is re-read from the database and
                  compared field by field against what the dump holds, through
                  the same decoder a restore would use. Catches an encoder that
                  silently mangles timestamps, JSON columns or numerics.

Exit code is non-zero if any check fails, so it can gate a backup job.
"""
from __future__ import annotations

import base64
import gzip
import json
import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio  # noqa: E402

from sqlalchemy import MetaData, func, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

SAMPLE_ROWS_PER_TABLE = 5


def _decode(v):
    """Inverse of the dump encoder — what a restore would apply."""
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
    """-> (meta, {table: [rows]}, footer_counts). Raises on a malformed file."""
    meta = None
    footer = None
    tables: dict[str, list[dict]] = {}
    current = None
    with gzip.open(path, "rt", encoding="utf-8") as fi:
        for lineno, line in enumerate(fi, 1):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"CORRUPT: line {lineno} is not valid JSON: {e}")
            if "_meta" in obj:
                meta = obj["_meta"]
            elif "_table" in obj:
                current = obj["_table"]
                tables.setdefault(current, [])
            elif "_end" in obj:
                footer = obj["counts"]
            else:
                if current is None:
                    raise SystemExit(f"CORRUPT: row at line {lineno} before any table marker")
                tables[current].append(obj)
    if meta is None:
        raise SystemExit("CORRUPT: no header record — file is not a fairview logical dump")
    if footer is None:
        raise SystemExit("TRUNCATED: no end marker — the dump did not finish writing")
    return meta, tables, footer


async def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = Path(sys.argv[1])
    if not path.exists():
        raise SystemExit(f"No such file: {path}")

    print("=" * 78)
    print("BACKUP VERIFICATION")
    print("=" * 78)
    print(f"file : {path}")
    print(f"size : {path.stat().st_size:,} bytes")

    # ── 1. readable ───────────────────────────────────────────────────────────
    meta, tables, footer = read_dump(path)
    total_rows = sum(len(v) for v in tables.values())
    print("\n[1/3] READABLE")
    print(f"   format           : {meta.get('format')}")
    print(f"   created_at       : {meta.get('created_at')}")
    print(f"   server_version   : {meta.get('server_version')}")
    print(f"   alembic_revision : {meta.get('alembic_revision')}")
    print(f"   tables in file   : {len(tables)}")
    print(f"   rows in file     : {total_rows:,}")
    print("   header + end marker present, every line parsed  -> OK")

    mismatched_footer = {t: (len(rows), footer.get(t))
                         for t, rows in tables.items() if footer.get(t) != len(rows)}
    if mismatched_footer:
        print(f"   *** footer disagrees with body: {mismatched_footer}")
        return 1

    # ── 2 & 3. against the live database ──────────────────────────────────────
    db_url = sys.argv[2] if len(sys.argv) > 2 else None
    if db_url is None:
        cbt = (Path(__file__).with_name("backfill_cbt_assessments.py")).read_text()
        import re
        db_url = re.search(r'^DB_URL = "(.+)"', cbt, re.M).group(1)
    async_url = db_url.replace("postgresql://", "postgresql+asyncpg://").split("?")[0]

    # SSL only for remote hosts — a local drill target has no TLS listener.
    local = "@localhost" in async_url or "@127.0.0.1" in async_url
    connect_args = {} if local else {"ssl": "require"}
    engine = create_async_engine(async_url, connect_args=connect_args, pool_pre_ping=True)
    failures = 0
    try:
        async with engine.connect() as conn:
            md = MetaData()
            await conn.run_sync(md.reflect)

            print("\n[2/3] COMPLETE  (row counts vs the live database)")
            live_tables = {t.name for t in md.sorted_tables}
            missing = live_tables - set(tables)
            extra = set(tables) - live_tables
            if missing:
                print(f"   *** tables in the DB but NOT in the dump: {sorted(missing)}")
                failures += 1
            if extra:
                print(f"   *** tables in the dump but not in the DB: {sorted(extra)}")

            # One round trip for all ~270 counts. Looping cost full network
            # latency per table and the connection was being dropped mid-loop.
            count_sql = " UNION ALL ".join(
                "SELECT '" + t.name.replace("'", "''") + f"' AS t, COUNT(*) AS n FROM \"{t.name}\""
                for t in md.sorted_tables
            )
            live_counts = {r[0]: r[1] for r in (await conn.execute(text(count_sql))).all()}

            bad_counts = []
            nonempty = 0
            for t in md.sorted_tables:
                live = live_counts.get(t.name, 0)
                dumped = len(tables.get(t.name, []))
                if live != dumped:
                    bad_counts.append((t.name, live, dumped))
                if live:
                    nonempty += 1
            if bad_counts:
                for name, live, dumped in bad_counts:
                    print(f"   *** {name}: live={live} dumped={dumped}")
                failures += 1
            else:
                print(f"   all {len(live_tables)} tables match "
                      f"({nonempty} non-empty, {total_rows:,} rows) -> OK")

            print(f"\n[3/3] FAITHFUL  (up to {SAMPLE_ROWS_PER_TABLE} sampled rows/table, "
                  f"decoded and compared field by field)")
            rng = random.Random(20260902)
            checked_rows = checked_fields = 0
            diffs = []
            for t in md.sorted_tables:
                dumped_rows = tables.get(t.name, [])
                if not dumped_rows:
                    continue
                pk = [c.name for c in t.primary_key.columns]
                if not pk:
                    continue
                for row in rng.sample(dumped_rows, min(SAMPLE_ROWS_PER_TABLE, len(dumped_rows))):
                    where = [t.c[k] == _decode(row[k]) for k in pk]
                    live_row = (await conn.execute(select(t).where(*where))).mappings().first()
                    if live_row is None:
                        diffs.append(f"{t.name}: pk={[row[k] for k in pk]} not found live")
                        continue
                    checked_rows += 1
                    for col, live_val in live_row.items():
                        checked_fields += 1
                        if _decode(row[col]) != live_val:
                            diffs.append(f"{t.name}.{col}: dump={row[col]!r} live={live_val!r}")
            if diffs:
                failures += 1
                for d in diffs[:15]:
                    print(f"   *** {d}")
                print(f"   {len(diffs)} field mismatch(es)")
            else:
                print(f"   {checked_rows} rows / {checked_fields} fields compared, "
                      f"all identical -> OK")

            await conn.rollback()
    finally:
        await engine.dispose()

    print("\n" + "=" * 78)
    if failures:
        print(f"VERDICT: FAILED — {failures} check(s) did not pass")
    else:
        print("VERDICT: PASS — the dump is complete and faithful to the source")
        print(f"         Restore path: create an empty DB, `alembic upgrade "
              f"{meta.get('alembic_revision')}`, then load in the recorded table order.")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
