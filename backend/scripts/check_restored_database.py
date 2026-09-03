#!/usr/bin/env python
"""Application-level checks against a restored database.

  python scripts/check_restored_database.py <db-url>

Row counts prove nothing about whether the data is USABLE. These are the
questions a school would actually ask after a disaster:

  • are the headline record counts what we expect?
  • does a named pupil's record still resolve — user -> student -> class?
  • do their results still hang off them, and does the report-approval row that
    makes results visible still point at the right class?
  • do the foreign keys actually resolve, or did the restore leave orphans that
    the database would have rejected on a real INSERT?

The FK sweep is the important one: a data-only restore inserts rows directly, so
a referential mistake shows up as orphans rather than as an error.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import MetaData, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

EXPECTED = {
    "users": 777,
    "students": 450,
    "grades": 1800,
    "student_assessment_scores": 1800,
    "cbt_attempts": 1799,
    "report_approvals": 12,
    "parent_guardians": 450,
    "school_classes": 30,
    "roles": 44,
}


async def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    url = sys.argv[1]
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").split("?")[0]
    local = "@localhost" in async_url or "@127.0.0.1" in async_url
    engine = create_async_engine(async_url, connect_args={} if local else {"ssl": "require"})
    failures = 0

    try:
        async with engine.connect() as conn:
            print("=" * 78)
            print("APPLICATION-LEVEL CHECKS ON THE RESTORED DATABASE")
            print("=" * 78)

            # ── 1. headline counts ────────────────────────────────────────────
            print("\n[1] Expected record counts")
            for tbl, want in EXPECTED.items():
                got = (await conn.execute(text(f'SELECT COUNT(*) FROM "{tbl}"'))).scalar()
                ok = got == want
                failures += 0 if ok else 1
                print(f"   {tbl:<30} expected {want:>6}   got {got:>6}   "
                      f"{'OK' if ok else '*** MISMATCH ***'}")

            # ── 2. a named pupil, followed through the joins ──────────────────
            print("\n[2] Musa Yusuf — user -> student -> class -> results")
            row = (await conn.execute(text("""
                SELECT u.id AS user_id, u.email, u.full_name,
                       s.id AS student_id, s.student_id AS admission_no,
                       c.id AS class_id, c.name AS class_name, c.level
                FROM users u
                JOIN students s ON s.user_id = u.id
                JOIN school_classes c ON c.id = s.class_id
                WHERE u.full_name ILIKE '%Musa%Yusuf%'
                LIMIT 1
            """))).mappings().first()
            if not row:
                print("   *** could not resolve Musa Yusuf through the joins")
                failures += 1
            else:
                print(f"   user_id      : {row['user_id']}")
                print(f"   email        : {row['email']}")
                print(f"   student_id   : {row['student_id']}  (admission {row['admission_no']})")
                print(f"   class        : {row['class_name']} ({row['level']})")
                # user.id != student.id is the trap that cost us a bug this week;
                # assert the restore kept them distinct and both resolvable.
                assert row["user_id"] != row["student_id"]
                print("   user.id and student.id are distinct and both resolve -> OK")

                g = (await conn.execute(text("""
                    SELECT COUNT(*) n, COUNT(DISTINCT subject_id) subjects,
                           COUNT(*) FILTER (WHERE status = 'PUBLISHED') published
                    FROM grades WHERE student_id = :sid
                """), {"sid": row["student_id"]})).mappings().first()
                print(f"   grades       : {g['n']} rows across {g['subjects']} subjects, "
                      f"{g['published']} published")
                failures += 0 if g["n"] else 1

                sa = (await conn.execute(text(
                    "SELECT COUNT(*) FROM student_assessment_scores WHERE student_id = :sid"
                ), {"sid": row["student_id"]})).scalar()
                print(f"   assessments  : {sa} score rows")

                # ── 3. the row that makes results visible to a parent ─────────
                print("\n[3] The report_approval gating this pupil's class")
                ra = (await conn.execute(text("""
                    SELECT ra.id, ra.term, ra.stage, ra.academic_year, ra.notes,
                           ra.published_at IS NOT NULL AS stamped, c.name AS class_name
                    FROM report_approvals ra
                    JOIN school_classes c ON c.id = ra.class_id
                    WHERE ra.class_id = :cid
                """), {"cid": row["class_id"]})).mappings().all()
                if not ra:
                    print("   *** no report_approval row resolves for this class")
                    failures += 1
                for r in ra:
                    print(f"   {r['class_name']} / {r['term']} — stage={r['stage']} "
                          f"year={r['academic_year']} published_at_set={r['stamped']}")
                    print(f"     notes: {r['notes']}")

            # ── 4. referential integrity across every FK ──────────────────────
            print("\n[4] Foreign-key sweep — do all references resolve?")
            md = MetaData()
            await conn.run_sync(md.reflect)
            reflected_fks = sum(len(t.foreign_keys) for t in md.sorted_tables)
            if reflected_fks == 0:
                # A restore that did not finish its constraint phase leaves the
                # data in place with no FK constraints — reflecting the target
                # would then "check" nothing and pass vacuously. Fall back to the
                # application's own model definitions so the DATA is still tested
                # for referential consistency, which is the question that matters.
                print("   target declares no FK constraints — falling back to the "
                      "app's model metadata so this is not a vacuous pass")
                from app.database import Base
                from app.models import user, organization, role, audit, import_job  # noqa: F401
                from app.models import hrm, support, payment, hr_extended  # noqa: F401
                from app.models.modules import (  # noqa: F401
                    school, hospital, business, admissions, academics, pastoral,
                    finance, wallet, operations, platform, remita,
                )
                existing = {t.name for t in md.sorted_tables}
                md = Base.metadata
                # Only sweep tables the target actually has.
                md_tables = [t for t in md.sorted_tables if t.name in existing]
            else:
                md_tables = list(md.sorted_tables)
            # Every FK in ONE round trip. Issued one-by-one this is ~570 queries,
            # and against a remote database that is tens of minutes of pure
            # latency — long enough that the connection tends to be dropped
            # underneath it before the sweep finishes.
            parts, labels = [], []
            for t in md_tables:
                for fk in t.foreign_keys:
                    child, parent = fk.parent, fk.column
                    if parent.table.name not in {x.name for x in md_tables}:
                        continue
                    idx = len(labels)
                    labels.append(f"{t.name}.{child.name} -> "
                                  f"{parent.table.name}.{parent.name}")
                    parts.append(
                        f'SELECT {idx} AS i, COUNT(*) AS n FROM "{t.name}" c '
                        f'LEFT JOIN "{parent.table.name}" p '
                        f'ON c."{child.name}" = p."{parent.name}" '
                        f'WHERE c."{child.name}" IS NOT NULL AND p."{parent.name}" IS NULL'
                    )
            orphaned = 0
            if parts:
                rows = (await conn.execute(text(" UNION ALL ".join(parts)))).all()
                for i, n in rows:
                    if n:
                        orphaned += 1
                        failures += 1
                        print(f"   *** {labels[i]}: {n} orphan(s)")
            print(f"   {len(labels)} foreign keys checked, {orphaned} with orphans "
                  f"-> {'OK' if not orphaned else 'BROKEN'}")

            await conn.rollback()
    finally:
        await engine.dispose()

    print("\n" + "=" * 78)
    print("VERDICT: " + ("PASS — restored data is complete, linked and usable"
                         if not failures else f"FAILED — {failures} problem(s)"))
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
