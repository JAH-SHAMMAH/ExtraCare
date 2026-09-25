"""Align the early-years structure with Fairview's real one (their live Educare).

Educare IS Fairview's current system, so its structure is authoritative:

    Early Years (section)
      Playgroup     -> "Playgroup"
      Pre-Nursery   -> "Pre-Nursery Lilac", "Pre-Nursery Lillies"
      Nursery       -> "Nursery Maples", "Nursery Blossom"
      Reception     -> "Reception Olive", "Reception Tulip"

Ours says section "Nursery", classes "Nursery A/B", "Reception A/B" and a year
group "Early-Years" with two classes.

WHAT THIS SCRIPT DOES NOT DO: it does not touch Early-Years A/B. Those two
classes hold 30 real children, and mapping them onto Pre-Nursery is an inference
from the class COUNT matching, not a fact anyone has confirmed. Renaming the
group those children belong to is the one step here with real consequence for
real records, so it waits for an explicit yes. Everything else is a label.

SAFETY. Class names are matched by id everywhere, never by name (checked), so
renaming a class moves nothing and orphans nothing - pupils, teachers, marks and
timetable rows all hang off class_id. `school_classes.level` IS name-matched, by
assessments.year_group / report_level_settings / report_subject_exclusions /
result_default_comments / subject_groups - but every one of those is empty today,
which is exactly why this is cheap NOW and expensive once Report Setup is
configured.

The section rename also sets level_aliases. Auto-map links a class whose level
matches the section NAME or an alias; with aliases null, renaming Nursery ->
Early Years would quietly stop matching Nursery/Reception if anyone ever ran
auto-map again.

DRY RUN BY DEFAULT.

    python -m scripts.align_early_years "<DSN>"
    python -m scripts.align_early_years "<DSN>" --write
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import SchoolSection
from app.models.modules.school import SchoolClass, Student, YearGroup

SECTION_FROM, SECTION_TO = "Nursery", "Early Years"

# The levels that belong to the Early Years section, including the two not yet
# created and "Early-Years" while it still exists.
SECTION_ALIASES = ["Playgroup", "Pre-Nursery", "Nursery", "Reception", "Early-Years"]

# (current name -> Fairview's real name). Label only; the row, its id, its pupils
# and its teacher are untouched.
CLASS_RENAMES = {
    "Nursery A": "Nursery Maples",
    "Nursery B": "Nursery Blossom",
    "Reception A": "Reception Olive",
    "Reception B": "Reception Tulip",
}

# New, empty. Playgroup has no pupils yet at Fairview.
NEW_YEAR_GROUP = {"name": "Playgroup", "short_code": "PG", "position": 0}
NEW_CLASS = {"name": "Playgroup", "level": "Playgroup"}

HELD = ("Early-Years A", "Early-Years B")


def _dsn() -> str:
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            return a.split("?")[0]
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env.split("?")[0]
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def main() -> int:
    write = "--write" in sys.argv
    engine = create_async_engine(_dsn(), echo=False, connect_args={"ssl": "require"})
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        print(f"{'WRITE' if write else 'DRY RUN'}\n")
        planned = 0

        # ── 1. section ────────────────────────────────────────────────────────
        sec = (await db.execute(
            select(SchoolSection).where(SchoolSection.name == SECTION_FROM)
        )).scalars().first()
        already = (await db.execute(
            select(SchoolSection).where(SchoolSection.name == SECTION_TO)
        )).scalars().first()
        if already:
            print(f"section   = already '{SECTION_TO}' — nothing to do")
        elif sec:
            n = (await db.execute(
                select(SchoolClass).where(SchoolClass.section_id == sec.id)
            )).scalars().all()
            print(f"section   + '{SECTION_FROM}' -> '{SECTION_TO}'  ({len(n)} classes keep their section_id)")
            print(f"            level_aliases -> {SECTION_ALIASES}")
            planned += 1
            if write:
                sec.name = SECTION_TO
                sec.level_aliases = SECTION_ALIASES
        else:
            print(f"section   ! neither '{SECTION_FROM}' nor '{SECTION_TO}' found — skipped")

        # ── 2. class renames ──────────────────────────────────────────────────
        print()
        for old, new in CLASS_RENAMES.items():
            row = (await db.execute(select(SchoolClass).where(SchoolClass.name == old))).scalars().first()
            if not row:
                done = (await db.execute(select(SchoolClass).where(SchoolClass.name == new))).scalars().first()
                print(f"class     {'= already ' + new if done else '! ' + old + ' not found'}")
                continue
            pupils = (await db.execute(
                select(Student).where(Student.class_id == row.id, Student.is_deleted == False)  # noqa: E712
            )).scalars().all()
            print(f"class     + {old:<14} -> {new:<18} ({len(pupils)} pupils stay put — same row, same id)")
            planned += 1
            if write:
                row.name = new

        # ── 3. Playgroup, empty ───────────────────────────────────────────────
        print()
        yg = (await db.execute(select(YearGroup).where(YearGroup.name == NEW_YEAR_GROUP["name"]))).scalars().first()
        cls = (await db.execute(select(SchoolClass).where(SchoolClass.name == NEW_CLASS["name"]))).scalars().first()
        org_id = (sec or already).org_id if (sec or already) else None
        if yg:
            print(f"yeargroup = '{NEW_YEAR_GROUP['name']}' already exists")
        else:
            print(f"yeargroup + '{NEW_YEAR_GROUP['name']}' (position {NEW_YEAR_GROUP['position']}, before Early-Years)")
            planned += 1
            if write:
                db.add(YearGroup(id=str(uuid.uuid4()), org_id=org_id, **NEW_YEAR_GROUP))
        if cls:
            print(f"class     = '{NEW_CLASS['name']}' already exists")
        else:
            print(f"class     + '{NEW_CLASS['name']}' — EMPTY, no pupils, in {SECTION_TO}")
            planned += 1
            if write:
                db.add(SchoolClass(id=str(uuid.uuid4()), org_id=org_id,
                                   section_id=(sec or already).id if (sec or already) else None,
                                   **NEW_CLASS))

        # ── 4. what is deliberately untouched ─────────────────────────────────
        print()
        held = (await db.execute(select(SchoolClass).where(SchoolClass.name.in_(HELD)))).scalars().all()
        total = 0
        for h in held:
            n = len((await db.execute(
                select(Student).where(Student.class_id == h.id, Student.is_deleted == False)  # noqa: E712
            )).scalars().all())
            total += n
            print(f"HELD      . {h.name:<14} ({n} pupils) — NOT renamed")
        if held:
            print(f"            Mapping these onto Pre-Nursery is inferred from the class")
            print(f"            count, not confirmed. {total} real children; needs an explicit yes.")

        if write:
            await db.commit()
            print(f"\n[OK] {planned} change(s) applied.")
        else:
            print(f"\nDRY RUN — nothing written. {planned} change(s) would be made.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
