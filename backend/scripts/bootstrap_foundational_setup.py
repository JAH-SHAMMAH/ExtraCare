"""
Bootstrap foundational setup data for Fairview School: academic session,
school sections (Nursery/Primary/Secondary), and year groups.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_foundational_setup "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_foundational_setup "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os
from datetime import date

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_foundational_setup <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import AcademicSession, SchoolSection
from app.models.modules.school import YearGroup


FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

ACADEMIC_SESSION = {
    "name": "2025/2026",
    "term": "Term 1",
    "start_date": date(2025, 9, 15),
    "end_date": date(2025, 12, 12),
    "is_current": True,
}

SECTIONS = [
    {"name": "Nursery", "curriculum": "eyfs", "position": 1},
    {"name": "Primary", "curriculum": "nigerian", "position": 2},
    {"name": "Secondary", "curriculum": "nigerian", "position": 3},
]

# (name, short_code, category, position)
YEAR_GROUPS = [
    ("Early-Years", "EY", "active", 1),
    ("Nursery", "N", "active", 2),
    ("Reception", "R", "active", 3),
    ("Year 1", "Y1", "active", 4),
    ("Year 2", "Y2", "active", 5),
    ("Year 3", "Y3", "active", 6),
    ("Year 4", "Y4", "active", 7),
    ("Year 5", "Y5", "active", 8),
    ("Year 6", "Y6", "active", 9),
    ("JSS1", "Y7", "active", 10),
    ("JSS2", "Y8", "active", 11),
    ("JSS3", "Y9", "active", 12),
    ("SSS1", "Y10", "active", 13),
    ("SSS2", "Y11", "active", 14),
    ("SSS3", "Y12", "active", 15),
]


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. CHECK: Does an academic session already exist for this org?
        existing_session = (await db.execute(
            select(AcademicSession).where(AcademicSession.org_id == FAIRVIEW_ORG_ID)
        )).scalars().first()

        existing_sections = (await db.execute(
            select(SchoolSection).where(SchoolSection.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        existing_year_groups = (await db.execute(
            select(YearGroup).where(YearGroup.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if existing_session or existing_sections or existing_year_groups:
            print("Foundational data already exists for this org — nothing to do:")
            print(f"  Academic sessions: {len((existing_session,) if existing_session else ())}")
            print(f"  School sections:   {len(existing_sections)}")
            print(f"  Year groups:       {len(existing_year_groups)}")
            await engine.dispose()
            return 0

        # 2. DRY-RUN: Show what will be created
        print("=" * 70)
        print("DRY-RUN: The following foundational setup data will be created:")
        print("=" * 70)
        print()
        print("Academic Session:")
        print(f"  Name: {ACADEMIC_SESSION['name']}  Term: {ACADEMIC_SESSION['term']}  (current)")
        print()
        print("School Sections (3):")
        for s in SECTIONS:
            print(f"  - {s['name']:<12} curriculum={s['curriculum']}")
        print()
        print(f"Year Groups ({len(YEAR_GROUPS)}):")
        for name, code, category, pos in YEAR_GROUPS:
            print(f"  {pos:>2}. {name:<14} ({code})")
        print()
        print("=" * 70)

        if not write_mode:
            print()
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create this data:")
            print()
            print(f'  python -m scripts.bootstrap_foundational_setup "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        # 3. WRITE
        print()
        print("Writing to database...")
        print()

        session = AcademicSession(org_id=FAIRVIEW_ORG_ID, **ACADEMIC_SESSION)
        db.add(session)

        for s in SECTIONS:
            db.add(SchoolSection(org_id=FAIRVIEW_ORG_ID, **s))

        for name, code, category, pos in YEAR_GROUPS:
            db.add(YearGroup(
                org_id=FAIRVIEW_ORG_ID,
                name=name,
                short_code=code,
                category=category,
                position=pos,
            ))

        await db.commit()

        print("✓ Foundational setup data created successfully!")
        print(f"  1 academic session, {len(SECTIONS)} sections, {len(YEAR_GROUPS)} year groups")
        print()
        print("Next step: Create school classes (e.g. JSS1A) linked to sections and year groups")

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
