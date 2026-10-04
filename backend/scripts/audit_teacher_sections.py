"""READ-ONLY audit of the two competing sources of a teacher's sections.

Answers three questions, and writes nothing.

  1. How many rows does `teacher_sections` actually hold?
  2. Which teachers' access would CHANGE if the report gates derived sections
     the way `/auth/me` already does (from `SchoolClass.teacher_id`) instead of
     from the `teacher_sections` table?
  3. Did any role lose leave read-all unintentionally when that gate moved off
     `users:read` (commit 54e3ef9)?

RUN ON PRODUCTION 2026-10-04 -- RESULT: GAP 2 IS CLOSED, NO CHANGE NEEDED.
    teacher_sections            15 rows
    classes                     31, all sectioned
    class teachers              15, ALL already hold a matching row
    would change                0
    would lose access           0
    alembic_version             138

So the two sources agree today, and the gate was left exactly as it is. THE
INVARIANT THIS DEPENDS ON, and the one thing that would reopen the gap:

    a class teacher assigned to a class WITHOUT a matching `teacher_sections`
    row is locked out of that class's report card, broadsheet and Result
    Analysis, and sees an EMPTY dropdown rather than an error.

Nothing enforces that pairing. `SchoolClass.teacher_id` is set from class
admin; `teacher_sections` is written only by the Teachers module's
Assign-To-School flow. Assign a class teacher without also assigning their
school and the two drift apart silently -- the sidebar keeps offering the
report section, because `/auth/me` derives it from the class, while the gate
refuses. Re-run this script after any bulk class-teacher change.

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
import json
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

        print("\n[5] CUSTOM ROLES THAT LOST LEAVE READ-ALL (commit 54e3ef9)")
        print("    Reading another member of staff's leave moved from `users:read`")
        print("    to `hr:write` OR `users:write`. The 45 shipped presets were")
        print("    enumerated before that landed, but a role created through the UI")
        print("    could hold `users:read` and neither of the new two -- those are")
        print("    the only roles that lost access unintentionally.")
        role_rows = await conn.fetch("""
            SELECT r.id, r.name, r.slug, r.is_system, r.permissions,
                   (SELECT count(*) FROM user_roles ur WHERE ur.role_id = r.id) AS holders
              FROM roles r ORDER BY r.is_system, r.name""")

        def satisfies(perms: set[str], scope: str) -> bool:
            """Mirror leave.py::_has_scope exactly -- '*' and 'ns:*' only."""
            if "*" in perms or scope in perms:
                return True
            return f"{scope.split(':', 1)[0]}:*" in perms

        affected, kept = [], 0
        for r in role_rows:
            raw = r["permissions"]
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (TypeError, ValueError):
                    raw = []
            perms = set(raw or [])
            if not satisfies(perms, "users:read"):
                continue          # never had read-all; nothing to lose
            if satisfies(perms, "hr:write") or satisfies(perms, "users:write"):
                kept += 1         # still allowed under the new gate
                continue
            affected.append((r, perms))

        print(f"\n    roles examined: {len(role_rows)}")
        print(f"    had read-all and KEEP it:  {kept}")
        print(f"    had read-all and LOST it:  {len(affected)}")
        if not affected:
            print("    -> nobody lost access unintentionally.")
        else:
            print(f"\n      {'role':28} {'slug':22} {'system?':8} holders")
            for r, perms in affected:
                flag = "preset" if r["is_system"] else "CUSTOM"
                print(f"      {r['name'][:27]:28} {(r['slug'] or '')[:21]:22} "
                      f"{flag:8} {r['holders']}")
            custom = [r for r, _ in affected if not r["is_system"]]
            live = [r for r, _ in affected if r["holders"]]
            print(f"\n    CUSTOM among them: {len(custom)}")
            print(f"    WITH AT LEAST ONE HOLDER (i.e. a real person affected): {len(live)}")
            if live:
                print("    -> to restore one, grant it `hr:write` (HR administrator)")
                print("       or `users:write` (user administrator). Do NOT put")
                print("       `users:read` back as the gate: 17 presets hold it.")

        print("\n[6] SCHEMA VERSION (no migration is involved in this work)")
        print(f"    alembic_version: "
              f"{await conn.fetchval('SELECT version_num FROM alembic_version')}")
        print("=" * 72)
    finally:
        await conn.close()


asyncio.run(main())
