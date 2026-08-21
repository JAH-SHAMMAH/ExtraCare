"""
Bootstrap school classes (streams) for Fairview School: creates 2 classes
(A/B) per existing year group, linked to the correct school section.
teacher_id is left null — assign teachers in a follow-up step once real
teacher accounts exist.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_school_classes "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_school_classes "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_school_classes <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import SchoolSection
from app.models.modules.school import YearGroup, SchoolClass


FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"
ACADEMIC_YEAR = "2025/2026"
STREAMS = ["A", "B"]

# Maps a year group name to the school section it belongs to.
YEAR_GROUP_TO_SECTION = {
    "Early-Years": "Nursery",
    "Nursery": "Nursery",
    "Reception": "Nursery",
    "Year 1": "Primary",
    "Year 2": "Primary",
    "Year 3": "Primary",
    "Year 4": "Primary",
    "Year 5": "Primary",
    "Year 6": "Primary",
    "JSS1": "Secondary",
    "JSS2": "Secondary",
    "JSS3": "Secondary",
    "SSS1": "Secondary",
    "SSS2": "Secondary",
    "SSS3": "Secondary",
}


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. Load prerequisites
        year_groups = (await db.execute(
            select(YearGroup).where(YearGroup.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        sections = (await db.execute(
            select(SchoolSection).where(SchoolSection.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if not year_groups or not sections:
            print("ERROR: Year groups or school sections not found for this org.")
            print("Run bootstrap_foundational_setup.py first.")
            await engine.dispose()
            return 1

        section_by_name = {s.name: s for s in sections}

        existing_classes = (await db.execute(
            select(SchoolClass).where(SchoolClass.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if existing_classes:
            print(f"Found {len(existing_classes)} existing school classes for this org — nothing to do.")
            await engine.dispose()
            return 0

        # 2. Build the plan
        plan = []  # list of (class_name, level, section_name, section_id)
        skipped = []
        for yg in sorted(year_groups, key=lambda y: y.position):
            section_name = YEAR_GROUP_TO_SECTION.get(yg.name)
            section = section_by_name.get(section_name) if section_name else None
            if not section:
                skipped.append(yg.name)
                continue
            for stream in STREAMS:
                class_name = f"{yg.name} {stream}"
                plan.append((class_name, yg.name, section.name, section.id))

        # 3. DRY-RUN: Show what will be created
        print("=" * 70)
        print("DRY-RUN: The following school classes will be created:")
        print("=" * 70)
        print()
        current_section = None
        for class_name, level, section_name, _ in plan:
            if section_name != current_section:
                print(f"\n{section_name}:")
                current_section = section_name
            print(f"  - {class_name:<16} (level={level}, academic_year={ACADEMIC_YEAR}, teacher: unassigned)")
        print()
        print(f"Total: {len(plan)} classes")
        if skipped:
            print(f"\nSkipped (no matching section found): {', '.join(skipped)}")
        print()
        print("=" * 70)

        if not write_mode:
            print()
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create these classes:")
            print()
            print(f'  python -m scripts.bootstrap_school_classes "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        # 4. WRITE
        print()
        print("Writing to database...")
        print()

        for class_name, level, section_name, section_id in plan:
            db.add(SchoolClass(
                org_id=FAIRVIEW_ORG_ID,
                name=class_name,
                level=level,
                section_id=section_id,
                section=class_name[-1],  # "A" or "B"
                academic_year=ACADEMIC_YEAR,
                teacher_id=None,
                max_capacity=40,
            ))

        await db.commit()

        print(f"✓ {len(plan)} school classes created successfully!")
        print()
        print("Next step: Create teacher accounts, then assign teacher_id per class")

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
