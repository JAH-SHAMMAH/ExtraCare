"""
Bootstrap 10 Secondary school subjects for Fairview School.

Creates the standard Nigerian Secondary curriculum subjects (Mathematics,
English Language, Physics, Chemistry, Biology, Economics, Government, ICT,
CRS, Geography) as Subject rows, applied uniformly across all Secondary
classes (JSS1–3, SSS1–3). Each subject is scoped to the Fairview org.

ASSUMPTION: All 10 subjects apply to all Secondary classes equally (no
JSS-only / SSS-only / stream-specific subjects). This is a simplification
for placeholder data; real schools split JSS core vs SSS electives/streams.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_secondary_subjects "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_secondary_subjects "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_secondary_subjects <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import Subject

FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

# 10 subjects from seed_fairview_school.py: universal across all Secondary levels
SUBJECTS = [
    ("Mathematics", "Core numeracy and problem-solving"),
    ("English Language", "English language skills and literature"),
    ("Physics", "Physics and physical sciences"),
    ("Chemistry", "Chemistry and chemical sciences"),
    ("Biology", "Biology and life sciences"),
    ("Economics", "Economics and business principles"),
    ("Government", "Civics and government studies"),
    ("Information Technology", "ICT and computer literacy"),
    ("Christian Religious Studies", "Religious studies (CRS)"),
    ("Geography", "Geography and human/physical sciences"),
]


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    # Create async engine with proper SSL handling (strip ?ssl=require from URL)
    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Check for existing subjects (idempotent)
        existing = (await db.execute(
            select(Subject).where(Subject.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if existing:
            print(f"Found {len(existing)} existing subject records — nothing to do.")
            print("Existing subjects:")
            for subj in sorted(existing, key=lambda s: s.name):
                print(f"  - {subj.name}")
            await engine.dispose()
            return 0

        # Build the plan: (name, description)
        plan = list(SUBJECTS)

        print("=" * 70)
        print(f"DRY-RUN: {len(plan)} subjects will be created for Fairview Secondary")
        print("=" * 70)
        print()
        print("Subjects to create:")
        for name, description in plan:
            print(f"  - {name:<30} | {description}")
        print()
        print("=" * 70)
        print()
        print("ASSUMPTION CHECK:")
        print("  [+] All 10 subjects apply uniformly to all Secondary classes (JSS1-3, SSS1-3)")
        print("  [+] No JSS-only or SSS-only subjects (simplification for placeholder data)")
        print()

        if not write_mode:
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create these records:")
            print()
            print(f'  python -m scripts.bootstrap_secondary_subjects "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print("Writing to database...")
        print()

        for name, description in plan:
            subject = Subject(
                org_id=FAIRVIEW_ORG_ID,
                name=name,
                description=description,
            )
            db.add(subject)

        await db.commit()

        print(f"[OK] Created {len(plan)} subjects successfully!")
        print()
        print("Subjects created:")
        for name, description in plan:
            print(f"  [+] {name}")
        print()
        print("Next step: Run bootstrap_secondary_grading_scale.py to create the grading scale")
        print()

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
