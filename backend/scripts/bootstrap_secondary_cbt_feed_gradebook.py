"""
Bootstrap Secondary report gradebook from CBT exam results.

Processes all 120 CBT exams: for each exam, feeds student attempt scores as
Grade records to the gradebook, then publishes exam results to make them
visible on reports. This is the equivalent of an admin clicking "Publish results"
for each exam via the UI.

After this layer, students' CBT scores feed into their Secondary report cards
as EXAM grades (subject to the standard 40/60 CA/EXAM weighting).

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_secondary_cbt_feed_gradebook "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_secondary_cbt_feed_gradebook "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_secondary_cbt_feed_gradebook <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import CBTExam, CBTAttempt, Grade, GradeStatus
from app.models.user import User

FAIRVIEW_ORG_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"


async def _feed_gradebook_for_exam(
    db: AsyncSession, exam: CBTExam, org_id: str, actor: User
) -> int:
    """Feed grades from exam attempts to gradebook (same logic as publish_exam_results backend)."""
    # Get all graded attempts for this exam (excluding superseded)
    attempts = (await db.execute(
        select(CBTAttempt).where(
            CBTAttempt.exam_id == exam.id,
            CBTAttempt.status == "graded",
            CBTAttempt.superseded_at == None,
        )
    )).scalars().all()

    # Group by student (pick best score if multiple)
    student_attempts = {}
    for attempt in attempts:
        if attempt.student_id not in student_attempts:
            student_attempts[attempt.student_id] = attempt
        else:
            # Pick higher score
            if attempt.score > student_attempts[attempt.student_id].score:
                student_attempts[attempt.student_id] = attempt

    # Create/update Grade records (one per student per exam)
    fed_count = 0
    for student_id, attempt in student_attempts.items():
        # Normalize score to percentage (assuming attempt.max_score is 100)
        percentage = (attempt.score / attempt.max_score) * 100.0 if attempt.max_score > 0 else 0.0

        # Check if Grade already exists
        existing_grade = (await db.execute(
            select(Grade).where(
                Grade.exam_id == exam.id,
                Grade.student_id == student_id,
            )
        )).scalar_one_or_none()

        if existing_grade:
            # Update existing
            existing_grade.score = percentage
            existing_grade.status = GradeStatus.DRAFT
        else:
            # Create new
            grade = Grade(
                org_id=org_id,
                cbt_exam_id=exam.id,
                student_id=student_id,
                subject_id=exam.subject_id,
                term=exam.term,
                score=percentage,
                max_score=100.0,
                status=GradeStatus.DRAFT,
            )
            db.add(grade)

        fed_count += 1

    return fed_count


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    # Create async engine with proper SSL handling
    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Fetch all exams
        exams = (await db.execute(
            select(CBTExam).where(CBTExam.org_id == FAIRVIEW_ORG_ORG_ID)
        )).scalars().all()

        if not exams:
            print("ERROR: No CBT exams found.")
            await engine.dispose()
            return 1

        # Fetch an admin user for audit trail
        admin = (await db.execute(
            select(User).where(User.org_id == FAIRVIEW_ORG_ORG_ID)
        )).scalars().first()

        if not admin:
            print("ERROR: No user found in org.")
            await engine.dispose()
            return 1

        # Check for completion: we need ~1800 grades (180 students × 10 subjects)
        # If we have fewer, continue processing. If we have all, we're done.
        existing_grades = (await db.execute(
            select(Grade).where(Grade.org_id == FAIRVIEW_ORG_ORG_ID)
        )).scalars().all()

        # We expect 180 students × 10 subjects = 1800 grades
        # Allow some margin in case some students don't have attempts
        if len(existing_grades) >= 1750:
            print(f"Found {len(existing_grades)} existing Grade records — all complete!")
            await engine.dispose()
            return 0

        if existing_grades:
            print(f"Found {len(existing_grades)} existing Grade records — continuing...")
        else:
            print("No existing Grade records — starting fresh...")

        print("=" * 80)
        print(f"DRY-RUN: Grades will be fed from {len(exams)} CBT exams to the gradebook")
        print("=" * 80)
        print()
        print(f"Exams to process: {len(exams)}")
        print()
        print("For each exam:")
        print("  1. Read all GRADED student attempts")
        print("  2. Pick best score per student (if retakes)")
        print("  3. Create/update Grade record (DRAFT status)")
        print("  4. Grade feeds into report card as EXAM score (subject to 40/60 CA/EXAM weighting)")
        print()
        print("Sample exams to process:")
        for exam in exams[:10]:
            print(f"  - {exam.title}")
        if len(exams) > 10:
            print(f"  ... and {len(exams) - 10} more")
        print()
        print("Expected result:")
        print("  - ~1800 Grade records created (180 students × 10 subjects)")
        print("  - All grades transitioned to PUBLISHED (visible to parents/students)")
        print("  - CBT exam scores display at 100% value (no capping; no manual exams to trigger 60% weighting)")
        print("  - Report card totals = CBT scores (full value, since CA-type only)")
        print()
        print("=" * 80)
        print()

        if not write_mode:
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually feed grades and publish results:")
            print()
            print(f'  python -m scripts.bootstrap_secondary_cbt_feed_gradebook "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print("Writing to database (processing exams in batches of 10)...")
        print()

        import datetime
        total_fed = 0
        processed_exams = 0

        # Process exams in smaller batches to avoid long-running transactions
        for batch_start in range(0, len(exams), 10):
            batch_end = min(batch_start + 10, len(exams))
            batch = exams[batch_start:batch_end]

            for exam in batch:
                fed_count = await _feed_gradebook_for_exam(db, exam, FAIRVIEW_ORG_ORG_ID, admin)
                total_fed += fed_count
                processed_exams += 1

                # Publish exam results (set published_at and published_pass_percentage)
                exam.results_published_at = datetime.datetime.utcnow()
                exam.published_pass_percentage = exam.pass_percentage

            # Commit after each batch of 10 exams
            await db.commit()
            print(f"  [+] Processed {processed_exams} exams, fed {total_fed} grades")

        # Bulk publish all DRAFT grades created above
        # (Grade.status must be PUBLISHED for non-staff visibility)
        result = await db.execute(
            update(Grade).where(
                Grade.org_id == FAIRVIEW_ORG_ORG_ID,
                Grade.status == GradeStatus.DRAFT
            ).values(status=GradeStatus.PUBLISHED)
        )
        published_count = result.rowcount

        await db.commit()
        print(f"  [+] Published {published_count} grades for student visibility")

        print(f"[OK] Processed {processed_exams} exams, created {total_fed} grades, published {published_count}!")
        print()
        print(f"Exams processed:")
        for exam in exams[:10]:
            print(f"  [+] {exam.title} (results published, grades fed + published)")
        if len(exams) > 10:
            print(f"  ... and {len(exams) - 10} more")
        print()
        print(f"Total grades created: {total_fed}")
        print(f"Total grades published: {published_count}")
        print()
        print("Next step: Students can NOW see CBT exam scores on their Secondary report cards")
        print()

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
