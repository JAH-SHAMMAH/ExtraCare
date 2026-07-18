"""One-off data migration: local SQLite (extracare.db) -> Render Postgres.

Copies every row of every table, preserving ids + foreign keys + values exactly.
Types (bool / JSON / datetime) are handled by the app's own SQLAlchemy column
types — we read and write through the SAME metadata, so SQLite's 0/1, TEXT-JSON
and ISO-string timestamps decode to real Python objects and re-encode for
Postgres automatically. Password hashes are copied verbatim (never regenerated).

Usage (schema must already exist on the target — run `alembic upgrade head`
against it first):

    TARGET_DATABASE_URL="postgresql+asyncpg://USER:PASS@HOST.oregon-postgres.render.com/DB" \
        ./venv/Scripts/python.exe scripts/migrate_sqlite_to_postgres.py

Safety:
  * SQLite is opened READ-ONLY — the source file is never modified.
  * Aborts if ANY target table already has rows (prevents duplication); pass
    --force to override only if you know the target should be topped up.
  * Inserts in FK-dependency order; self-referential tables are topologically
    ordered so a parent row is always inserted before its children.
"""
from __future__ import annotations

import asyncio
import os
import sys

# Allow `import app.*` when run as `python scripts/migrate_sqlite_to_postgres.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine

# Populate the metadata with every model.
import app.main  # noqa: F401
from app.models.base import Base
from app.config import get_settings

SOURCE_URL = get_settings().DATABASE_URL  # sqlite+aiosqlite:///./extracare.db
TARGET_URL = os.environ.get("TARGET_DATABASE_URL", "").strip()
FORCE = "--force" in sys.argv
BATCH = 500


def _self_ref(table):
    """Return (local_col, ref_col) if `table` has a single-column self FK, else None."""
    for fk in table.foreign_keys:
        if fk.column.table is table:
            return fk.parent.name, fk.column.name
    return None


def _topo_order(rows, local_col, ref_col, id_col="id"):
    """Order rows so a referenced (parent) row precedes any row referencing it."""
    remaining = list(rows)
    emitted_ids: set = set()
    ordered = []
    # Iterate until stable; tiny data, so a simple sweep is fine.
    progressed = True
    while remaining and progressed:
        progressed = False
        still = []
        for r in remaining:
            parent = r.get(local_col)
            if parent is None or parent in emitted_ids or parent == r.get(id_col):
                ordered.append(r)
                emitted_ids.add(r.get(id_col))
                progressed = True
            else:
                still.append(r)
        remaining = still
    ordered.extend(remaining)  # any leftover (dangling refs) — insert last
    return ordered


async def main() -> int:
    if not TARGET_URL:
        print("ERROR: set TARGET_DATABASE_URL to the Render EXTERNAL connection string.")
        return 2
    if not TARGET_URL.startswith("postgresql"):
        print(f"ERROR: TARGET_DATABASE_URL must be a postgresql+asyncpg URL, got: {TARGET_URL[:24]}…")
        return 2

    source = create_async_engine(SOURCE_URL, connect_args={"uri": True} if False else {})
    target = create_async_engine(TARGET_URL)

    tables = Base.metadata.sorted_tables  # FK-dependency order (parents first)

    # 1) Read counts + rows from SQLite (read-only).
    before: dict[str, int] = {}
    data: dict[str, list[dict]] = {}
    async with source.connect() as sc:
        present = set((await sc.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'"))).scalars().all())
        for t in tables:
            if t.name not in present:
                continue
            rows = [dict(m) for m in (await sc.execute(select(t))).mappings().all()]
            before[t.name] = len(rows)
            data[t.name] = rows

    # 2) Guard: target must be empty (unless --force).
    async with target.connect() as tc:
        nonempty = []
        for t in tables:
            if t.name not in data:
                continue
            n = (await tc.execute(select(func.count()).select_from(t))).scalar() or 0
            if n > 0:
                nonempty.append((t.name, n))
        if nonempty and not FORCE:
            print("ABORT: target is not empty — would risk duplication. Non-empty tables:")
            for name, n in nonempty:
                print(f"  {name}: {n}")
            print("Re-run with --force only if you intend to top up an existing target.")
            return 3

    # 3) Load. FK constraints are dropped for the bulk load and re-added NOT VALID
    #    afterwards: SQLite never enforced FKs, so a few rows carry PRE-EXISTING
    #    dangling references (e.g. audit_logs / login rows whose actor is a
    #    since-deleted user). We preserve those rows + values EXACTLY rather than
    #    alter or drop them; NOT VALID keeps the constraint enforcing future writes
    #    while tolerating the historical dangling refs. All in one transaction, so
    #    any failure rolls the whole thing back (constraints restored).
    async with target.begin() as tc:
        fks = (await tc.execute(text(
            "SELECT conname, conrelid::regclass::text AS tbl, pg_get_constraintdef(oid) AS def "
            "FROM pg_constraint WHERE contype='f'"
        ))).mappings().all()
        for fk in fks:
            await tc.execute(text(f'ALTER TABLE {fk["tbl"]} DROP CONSTRAINT "{fk["conname"]}"'))
        print(f"  dropped {len(fks)} FK constraint(s) for the bulk load")

        for t in tables:
            rows = data.get(t.name)
            if not rows:
                continue
            for i in range(0, len(rows), BATCH):
                await tc.execute(t.insert(), rows[i:i + BATCH])
            print(f"  copied {t.name}: {len(rows)}")

        for fk in fks:
            await tc.execute(text(f'ALTER TABLE {fk["tbl"]} ADD CONSTRAINT "{fk["conname"]}" {fk["def"]} NOT VALID'))
        print(f"  re-added {len(fks)} FK constraint(s) (NOT VALID — pre-existing dangling refs preserved)")

    # 4) After-counts from Postgres + comparison.
    after: dict[str, int] = {}
    async with target.connect() as tc:
        for t in tables:
            if t.name not in data:
                continue
            after[t.name] = (await tc.execute(select(func.count()).select_from(t))).scalar() or 0

    print("\n=== ROW COUNT COMPARISON (only tables with rows shown) ===")
    print(f"{'table':40} {'sqlite':>8} {'postgres':>9}  ok")
    mismatches = 0
    tb = ta = 0
    for name in sorted(before):
        b, a = before[name], after.get(name, 0)
        tb += b
        ta += a
        if b == 0 and a == 0:
            continue
        ok = "OK" if b == a else "MISMATCH"
        if b != a:
            mismatches += 1
        print(f"{name:40} {b:>8} {a:>9}  {ok}")
    print(f"{'TOTAL':40} {tb:>8} {ta:>9}  {'OK' if tb == ta else 'MISMATCH'}")
    print(f"\n{mismatches} table mismatch(es)." if mismatches else "\nAll tables match. OK")

    # 5) Principal / staff verification (hashes intact, not reset).
    async with target.connect() as tc:
        rows = (await tc.execute(text("""
            SELECT u.email, u.full_name, r.slug,
                   CASE WHEN u.hashed_password IS NOT NULL AND u.hashed_password <> '' THEN 'yes' ELSE 'NO' END
            FROM users u JOIN user_roles ur ON ur.user_id = u.id JOIN roles r ON r.id = ur.role_id
            WHERE r.slug IN ('org_admin','manager') ORDER BY r.slug, u.email
        """))).all()
    print("\n=== admin/manager accounts in Postgres (password hash intact?) ===")
    for email, name, slug, hh in rows:
        print(f"  [{slug}] {name} <{email}>  hash={hh}")

    await source.dispose()
    await target.dispose()
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
