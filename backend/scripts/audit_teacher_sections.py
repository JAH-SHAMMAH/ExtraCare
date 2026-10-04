"""READ-ONLY audit of the two competing sources of a teacher's sections.

Answers two questions about gap 2, and writes nothing.

  1. How many rows does `teacher_sections` actually hold?
  2. Which teachers' access would CHANGE if the report gates derived sections
     the way `/auth/me` already does (from `SchoolClass.teacher_id`) instead of
     from the `teacher_sections` table?

BACKGROUND. `_class_for_reports_or_403` and `report_card` ask whether the
class's `section_id` appears in the caller's `teacher_sections` rows. But
`/auth/me` -- which decides whether the sidebar offers the report section at
all -- derives the same fact from the classes the user is class teacher of, and
says so in a comment. When the table is empty the two disagree: the nav offers
a door the gate then refuses, and `result_analysis_classes` returns an empty
dropdown.

Reaching either gate already requires `cls.teacher_id == user.id`, so the
section check can only ever reject someone the stronger class-teacher check has
already admitted. This script quantifies that rather than asserting it.

Usage:
    python scripts/audit_teacher_sections.py "<DATABASE_URL>"
    python scripts/audit_teacher_sections.py          # uses $DATABASE_URL

The DSN comes from argv or the environment, never from this file.
"""
from __future__ import annotations

import asyncio
import os
import sys

import asyncpg


def _dsn() -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env
    raise SystemExit(
        "Pass the DSN as the first argument, or set DATABASE_URL.\n"
        "  python scripts/audit_teacher_sections.py \"postgresql://...\"")


def _norm(dsn: str) -> str:
    # asyncpg wants plain postgresql://, not SQLAlchemy's +asyncpg form.
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> None:
    conn = await asyncpg.connect(
        _norm(_dsn()), timeout=180, command_timeout=300, ssl="require")
    try:
        print("=" * 72)
        print("[1] teacher_sections -- DOES THE TABLE HOLD ANYTHING?")
        total = await conn.fetchval("SELECT count(*) FROM teacher_sections")
        print(f"    rows: {total}")
        if total:
            for r in await conn.fetch("""
                SELECT s.name, count(*) n
                  FROM teacher_sections ts
                  JOIN school_sections s ON s.id = ts.section_id
                 GROUP BY s.name ORDER BY s.name"""):
                print(f"      {r['name']:18} {r['n']}")
        else:
            print("    EMPTY -- so every section check below is comparing against")
            print("    an empty set, and refuses every non-admin caller.")

        print("\n[2] CLASSES -- IS THE GATE EVEN ARMED?")
        print("    (the check is skipped when cls.section_id IS NULL)")
        for lbl, q in (
            ("classes total", "SELECT count(*) FROM school_classes"),
            ("with a section_id", "SELECT count(*) FROM school_classes WHERE section_id IS NOT NULL"),
            ("with a class teacher", "SELECT count(*) FROM school_classes WHERE teacher_id IS NOT NULL"),
            ("sectioned AND has a class teacher",
             "SELECT count(*) FROM school_classes "
             "WHERE section_id IS NOT NULL AND teacher_id IS NOT NULL"),
        ):
            print(f"    {lbl:36} {await conn.fetchval(q)}")

        print("\n[3] WHOSE ACCESS CHANGES UNDER THE SchoolClass.teacher_id DERIVATION?")
        rows = await conn.fetch("""
            SELECT u.id, u.full_name, u.email,
                   array_agg(DISTINCT c.name)       AS classes,
                   array_agg(DISTINCT s.name)       AS derived_sections,
                   (SELECT array_agg(DISTINCT s2.name)
                      FROM teacher_sections ts
                      JOIN school_sections s2 ON s2.id = ts.section_id
                     WHERE ts.teacher_id = u.id)    AS table_sections
              FROM school_classes c
              JOIN users u            ON u.id = c.teacher_id
              LEFT JOIN school_sections s ON s.id = c.section_id
             WHERE c.section_id IS NOT NULL
             GROUP BY u.id, u.full_name, u.email
             ORDER BY u.full_name""")

        gains, same = [], []
        for r in rows:
            derived = set(r["derived_sections"] or [])
            held = set(r["table_sections"] or [])
            # Blocked today for any section they are class teacher of but which
            # their teacher_sections rows do not cover.
            missing = derived - held
            (gains if missing else same).append((r, derived, held, missing))

        print(f"    class teachers of a sectioned class: {len(rows)}")
        print(f"      access WOULD CHANGE (blocked today): {len(gains)}")
        print(f"      access unchanged:                    {len(same)}")

        if gains:
            print("\n    BLOCKED TODAY -- 403 on their own class's report card,")
            print("    broadsheet and Result Analysis, with an empty dropdown:")
            print(f"      {'teacher':26} {'their sectioned class(es)':34} {'needs':12} holds")
            for r, derived, held, missing in gains:
                print(f"      {(r['full_name'] or r['email'])[:25]:26} "
                      f"{', '.join(sorted(r['classes'] or []))[:33]:34} "
                      f"{', '.join(sorted(missing))[:11]:12} "
                      f"{', '.join(sorted(held)) or '(none)'}")

        print("\n[4] THE OTHER DIRECTION -- would anyone LOSE access?")
        print("    A teacher_sections row for a section they are NOT class teacher")
        print("    of grants nothing on its own: both gates require")
        print("    cls.teacher_id == user.id FIRST. So a UNION can only widen, and")
        print("    a REPLACE could only narrow these rows:")
        extra = await conn.fetch("""
            SELECT u.full_name, u.email, s.name AS section
              FROM teacher_sections ts
              JOIN users u            ON u.id = ts.teacher_id
              JOIN school_sections s  ON s.id = ts.section_id
             WHERE NOT EXISTS (
                     SELECT 1 FROM school_classes c
                      WHERE c.teacher_id = ts.teacher_id
                        AND c.section_id = ts.section_id)
             ORDER BY u.full_name""")
        print(f"    rows granting a section the user teaches no class in: {len(extra)}")
        for r in extra:
            print(f"      {(r['full_name'] or r['email'])[:30]:32} {r['section']}")

        print("\n[5] SCHEMA VERSION (no migration is involved in this work)")
        print(f"    alembic_version: "
              f"{await conn.fetchval('SELECT version_num FROM alembic_version')}")
        print("=" * 72)
    finally:
        await conn.close()


asyncio.run(main())
