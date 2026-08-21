"""
Bootstrap CBT exams for Fairview School Secondary.

Creates one CBTExam per subject per Secondary class for the current term.
That's 10 subjects × 12 classes = 120 exams. Each exam is configured as:
  - max_attempts: 1 (single sitting)
  - pass_percentage: 50% (standard Secondary pass mark)
  - hold_results: False (results visible immediately)
  - status: DRAFT (ready for use but not yet live)

Exams are created with deterministic names and default settings. The actual
questions and student attempts are created by bootstrap_secondary_cbt_attempts.py.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_secondary_cbt_exams "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_secondary_cbt_exams "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_secondary_cbt_exams <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import SchoolClass, Subject, CBTExam, ExamStatus
from app.models.modules.platform import AcademicTerm

FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"
CURRENT_TERM = "Term 1"
CURRENT_ACADEMIC_YEAR = "2025/2026"


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    # Create async engine with proper SSL handling
    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Fetch SECONDARY classes only (JSS1-3, SSS1-3) and subjects
        # Filter by level to exclude Early-Years, Reception, Primary, etc.
        secondary_levels = ["JSS1", "JSS2", "JSS3", "SSS1", "SSS2", "SSS3"]
        classes = (await db.execute(
            select(SchoolClass).where(
                SchoolClass.org_id == FAIRVIEW_ORG_ID,
                SchoolClass.level.in_(secondary_levels)
            )
        )).scalars().all()

        subjects = (await db.execute(
            select(Subject).where(Subject.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if not classes:
            print("ERROR: No school classes found. Run bootstrap_secondary_subjects.py first.")
            await engine.dispose()
            return 1

        if not subjects:
            print("ERROR: No subjects found. Run bootstrap_secondary_subjects.py first.")
            await engine.dispose()
            return 1

        # Get the current term
        term = (await db.execute(
            select(AcademicTerm).where(
                AcademicTerm.org_id == FAIRVIEW_ORG_ID,
                AcademicTerm.name == CURRENT_TERM
            )
        )).scalar_one_or_none()

        if not term:
            print(f"ERROR: Academic term '{CURRENT_TERM}' not found. Run bootstrap_academic_terms.py first.")
            await engine.dispose()
            return 1

        # Check for existing CBT exams (idempotent)
        existing = (await db.execute(
            select(CBTExam).where(CBTExam.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if existing:
            print(f"Found {len(existing)} existing CBT exam records — nothing to do.")
            await engine.dispose()
            return 0

        # Build the plan: (class_id, class_name, subject_id, subject_name)
        plan = []
        for c in sorted(classes, key=lambda x: x.name):
            for s in sorted(subjects, key=lambda x: x.name):
                plan.append((c.id, c.name, s.id, s.name))

        print("=" * 80)
        print(f"DRY-RUN: {len(plan)} CBT exams will be created for Fairview Secondary")
        print("=" * 80)
        print()
        print(f"Exams per class: {len(subjects)} subjects")
        print(f"Total classes: {len(classes)}")
        print(f"Total exams: {len(plan)} (1 per subject per class)")
        print()
        print("Sample exams to create:")
        for class_id, class_name, subject_id, subject_name in plan[:15]:
            exam_name = f"{subject_name} - {class_name}"
            print(f"  - {exam_name}")
        if len(plan) > 15:
            print(f"  ... and {len(plan) - 15} more")
        print()
        print("Defaults for each exam:")
        print(f"  - Term: {CURRENT_TERM}")
        print(f"  - Max attempts: 1 (single sitting)")
        print(f"  - Pass percentage: 50%")
        print(f"  - Results hold: No (results visible immediately)")
        print(f"  - Status: PUBLISHED (required for students to start attempts)")
        print()
        print("=" * 80)
        print()

        if not write_mode:
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create these exams:")
            print()
            print(f'  python -m scripts.bootstrap_secondary_cbt_exams "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print("Writing to database (this may take a moment for 120 exams)...")
        print()

        # Get a fake admin user (using the first user in the org)
        from app.models.user import User
        admin = (await db.execute(
            select(User).where(User.org_id == FAIRVIEW_ORG_ID)
        )).scalars().first()

        if not admin:
            print("ERROR: No user found in org. Cannot create exams without a creator.")
            await engine.dispose()
            return 1

        # Create the exams
        created_count = 0
        for class_id, class_name, subject_id, subject_name in plan:
            exam = CBTExam(
                org_id=FAIRVIEW_ORG_ID,
                title=f"{subject_name} - {class_name}",
                description=f"CBT exam for {subject_name} ({class_name})",
                class_id=class_id,
                subject_id=subject_id,
                term=CURRENT_TERM,
                created_by=admin.id,
                max_attempts=1,
                pass_percentage=50,
                hold_results=False,
                total_points=0.0,  # Will be set when questions are added
                status=ExamStatus.PUBLISHED,  # Required for students to start attempts in Layer 4
            )
            db.add(exam)
            created_count += 1

        await db.commit()

        print(f"[OK] Created {created_count} CBT exams successfully!")
        print()
        print(f"Sample exams created:")
        for class_id, class_name, subject_id, subject_name in plan[:10]:
            exam_name = f"{subject_name} - {class_name}"
            print(f"  [+] {exam_name}")
        if len(plan) > 10:
            print(f"  ... and {len(plan) - 10} more")
        print()
        print("Next step: Run bootstrap_secondary_cbt_attempts.py to generate student scores")
        print()

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
