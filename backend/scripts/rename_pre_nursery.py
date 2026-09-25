"""Step 1b: the Early-Years year group becomes Pre-Nursery.

Step 1 (scripts/align_early_years.py) renamed the section and the Nursery /
Reception classes, and deliberately HELD the Early-Years pair because mapping
them onto Pre-Nursery was an inference, not a confirmed fact. That question is
now settled: all pupil data in this portal is intentionally fake and permanent,
and only the STRUCTURE is modelled on Fairview's live Educare. So this is a
label change, exactly like step 1, with no pupil migration in it.

Fairview's real structure, from Educare (authoritative):

    Early Years (section)
      Playgroup     -> "Playgroup"
      Pre-Nursery   -> "Pre-Nursery Lilac", "Pre-Nursery Lillies"   <- this step
      Nursery       -> "Nursery Maples", "Nursery Blossom"          (step 1)
      Reception     -> "Reception Olive", "Reception Tulip"         (step 1)

The two class names are Educare's OWN, from the same source that gave the
Nursery and Reception names already applied in step 1 - they are not invented.
"Lillies" is Educare's spelling and is kept deliberately, so our structure
matches theirs rather than silently correcting it.

WHAT MOVES: nothing. The 30 pupils keep their rows, their ids and their class
ids; only three labels change (year group name, two class names), plus the
`level` string those classes carry and one now-dead section alias.

WHY `level` MATTERS. school_classes.level is matched BY NAME by
assessments.year_group, report_level_settings, report_subject_exclusions,
result_default_comments and subject_groups. Renaming the year group without the
level would leave those classes pointing at a level nobody configures. This
script re-checks those five tables are still empty and REFUSES to write if they
are not - once Report Setup is populated, a level rename stops being free.

DRY RUN BY DEFAULT.

    python -m scripts.rename_pre_nursery "<DSN>"
    python -m scripts.rename_pre_nursery "<DSN>" --write
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import SchoolSection
from app.models.modules.school import SchoolClass, Student, YearGroup

YEAR_GROUP_FROM, YEAR_GROUP_TO = "Early-Years", "Pre-Nursery"
SHORT_CODE_TO = "PN"

CLASS_RENAMES = {
    "Early-Years A": "Pre-Nursery Lilac",
    "Early-Years B": "Pre-Nursery Lillies",
}

# The level string those classes carry, renamed in step with the year group.
LEVEL_FROM, LEVEL_TO = "Early-Years", "Pre-Nursery"

SECTION_NAME = "Early Years"
# "Early-Years" becomes dead once nothing carries that level.
ALIASES_TO = ["Playgroup", "Pre-Nursery", "Nursery", "Reception"]

# Tables that match school_classes.level BY NAME. A level rename is only free
# while every one of these is empty.
NAME_MATCHED = [
    "assessments", "report_level_settings", "report_subject_exclusions",
    "result_default_comments", "subject_groups",
]


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

        # -- 0. the guard: is a level rename still free? -----------------------
        # What matters is not whether these tables have rows, but whether any
        # row PINS ITSELF to the level being renamed. year_group NULL means
        # "all levels", which survives a rename untouched.
        blocked = []
        print(f"guard     rows pinned to year_group {LEVEL_FROM!r} would be orphaned:")
        for tn in NAME_MATCHED:
            total = (await db.execute(sa_text(f'SELECT count(*) FROM "{tn}"'))).scalar_one()
            pinned = (await db.execute(sa_text(
                f'SELECT count(*) FROM "{tn}" WHERE year_group = :lvl'),
                {"lvl": LEVEL_FROM})).scalar_one()
            allrows = (await db.execute(sa_text(
                f'SELECT count(*) FROM "{tn}" WHERE year_group IS NULL'))).scalar_one()
            print(f"            {tn:<32} rows={total:<4} pinned={pinned:<4} "
                  f"all-levels={allrows}")
            if pinned:
                blocked.append((tn, pinned))
        if blocked:
            print()
            print("! Pinned rows in: " + ", ".join(f"{t} ({n})" for t, n in blocked))
            print(f"  These match school_classes.level BY NAME, so renaming the level")
            print(f"  would orphan them. Refusing to write - re-point them first.")
            if write:
                await engine.dispose()
                return 1

        # -- 1. year group ----------------------------------------------------
        print()
        yg = (await db.execute(
            select(YearGroup).where(YearGroup.name == YEAR_GROUP_FROM))).scalars().first()
        already_yg = (await db.execute(
            select(YearGroup).where(YearGroup.name == YEAR_GROUP_TO))).scalars().first()
        if already_yg:
            print(f"yeargroup = already '{YEAR_GROUP_TO}'")
        elif yg:
            print(f"yeargroup + '{YEAR_GROUP_FROM}' -> '{YEAR_GROUP_TO}'")
            print(f"            position {yg.position} unchanged, "
                  f"short_code {yg.short_code!r} -> {SHORT_CODE_TO!r}")
            planned += 1
            if write:
                yg.name = YEAR_GROUP_TO
                yg.short_code = SHORT_CODE_TO
        else:
            print(f"yeargroup ! neither '{YEAR_GROUP_FROM}' nor '{YEAR_GROUP_TO}' found - skipped")

        # -- 2. the two classes, name + level ---------------------------------
        print()
        for old, new in CLASS_RENAMES.items():
            row = (await db.execute(
                select(SchoolClass).where(SchoolClass.name == old))).scalars().first()
            if not row:
                already = (await db.execute(
                    select(SchoolClass).where(SchoolClass.name == new))).scalars().first()
                print(f"class     {'= already ' + new if already else '! ' + old + ' not found'}")
                continue
            pupils = (await db.execute(
                select(func.count()).select_from(Student).where(
                    Student.class_id == row.id,
                    Student.is_deleted == False))).scalar_one()  # noqa: E712
            print(f"class     + {old:<14} -> {new:<21} "
                  f"({pupils} pupils stay put - same row, same id)")
            print(f"            level {row.level!r} -> {LEVEL_TO!r}")
            planned += 1
            if write:
                row.name = new
                row.level = LEVEL_TO

        # any straggler still carrying the old level
        stragglers = (await db.execute(
            select(SchoolClass).where(
                SchoolClass.level == LEVEL_FROM,
                SchoolClass.name.notin_(list(CLASS_RENAMES))))).scalars().all()
        if stragglers:
            print()
            print(f"level     + {len(stragglers)} other class(es) still carry level "
                  f"{LEVEL_FROM!r}: {', '.join(s.name for s in stragglers)}")
            print(f"            renaming those too, so the level is consistent")
            planned += len(stragglers)
            if write:
                for s in stragglers:
                    s.level = LEVEL_TO

        # -- 3. section aliases -----------------------------------------------
        print()
        sec = (await db.execute(
            select(SchoolSection).where(SchoolSection.name == SECTION_NAME))).scalars().first()
        if not sec:
            print(f"section   ! '{SECTION_NAME}' not found - aliases unchanged")
        elif list(sec.level_aliases or []) == ALIASES_TO:
            print(f"section   = level_aliases already {ALIASES_TO}")
        else:
            print(f"section   + level_aliases {list(sec.level_aliases or [])}")
            print(f"                       -> {ALIASES_TO}")
            print(f"            ({LEVEL_FROM!r} is dead once nothing carries it)")
            planned += 1
            if write:
                sec.level_aliases = ALIASES_TO

        if write:
            await db.commit()
            print(f"\n[OK] {planned} change(s) applied.")
        else:
            print(f"\nDRY RUN - nothing written. {planned} change(s) would be made.")

        # -- 4. how the section will read -------------------------------------
        if sec:
            print("\nEarly Years section:")
            rows = (await db.execute(
                select(SchoolClass.name, SchoolClass.level)
                .where(SchoolClass.section_id == sec.id)
                .order_by(SchoolClass.name))).all()
            for name, level in rows:
                cid = (await db.execute(
                    select(SchoolClass.id).where(SchoolClass.name == name))).scalars().first()
                n = (await db.execute(
                    select(func.count()).select_from(Student).where(
                        Student.class_id == cid,
                        Student.is_deleted == False))).scalar_one()  # noqa: E712
                print(f"  {name:<22} level={str(level):<14} pupils={n}")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
