"""
Bootstrap CBT student attempts for Fairview School Secondary.

Creates one CBTAttempt per student per exam (one attempt per subject per student).
That's 180 students × 10 subjects per class = 1800 attempts total. Each attempt
includes a realistic score (normal distribution around 60-70%).

Attempts are created as GRADED status (reflecting a completed, marked exam) with
scores that feed into the gradebook in Layer 5 (_feed_gradebook).

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_secondary_cbt_attempts "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_secondary_cbt_attempts "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os
import random
from datetime import datetime, timedelta

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_secondary_cbt_attempts <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import CBTExam, Student, CBTAttempt, AttemptStatus
from app.models.modules.platform import AcademicTerm

FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"
CURRENT_TERM = "Term 1"

# Score generation: normal distribution centered on 65 (mean), stdev 18
# This gives realistic spread: ~68% pass (50th percentile +1 SD), ~95% within 29-101 range
SCORE_MEAN = 65.0
SCORE_STDEV = 18.0
MIN_SCORE = 0.0
MAX_SCORE = 100.0


def generate_realistic_score(rng: random.Random) -> float:
    """Generate a realistic exam score (normal distribution, clamped to 0-100)."""
    score = rng.gauss(SCORE_MEAN, SCORE_STDEV)
    return max(MIN_SCORE, min(MAX_SCORE, score))


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    # Create async engine with proper SSL handling
    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Fetch all exams and students
        exams = (await db.execute(
            select(CBTExam).where(CBTExam.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        students = (await db.execute(
            select(Student).where(Student.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if not exams:
            print("ERROR: No CBT exams found. Run bootstrap_secondary_cbt_exams.py first.")
            await engine.dispose()
            return 1

        if not students:
            print("ERROR: No students found. Run bootstrap_students.py first.")
            await engine.dispose()
            return 1

        # Check for existing attempts (idempotent)
        existing = (await db.execute(
            select(CBTAttempt).where(CBTAttempt.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if existing:
            print(f"Found {len(existing)} existing CBT attempt records — nothing to do.")
            await engine.dispose()
            return 0

        # Group students by class
        students_by_class = {}
        for student in students:
            class_id = student.class_id
            if class_id not in students_by_class:
                students_by_class[class_id] = []
            students_by_class[class_id].append(student)

        # Group exams by class
        exams_by_class = {}
        for exam in exams:
            class_id = exam.class_id
            if class_id not in exams_by_class:
                exams_by_class[class_id] = []
            exams_by_class[class_id].append(exam)

        # Build the plan: (student_id, exam_id, score)
        # Only include students in classes that have Secondary exams
        plan = []
        secondary_students_count = 0
        for class_id, class_students in students_by_class.items():
            class_exams = exams_by_class.get(class_id, [])
            if not class_exams:
                continue
            secondary_students_count += len(class_students)
            # Each student in the class takes each exam for the class
            for student in class_students:
                for exam in class_exams:
                    plan.append((student.id, exam.id, None))  # Score will be generated later

        print("=" * 80)
        print(f"DRY-RUN: {len(plan)} CBT attempts will be created for Fairview Secondary")
        print("=" * 80)
        print()
        print(f"Students (Secondary only): {secondary_students_count}")
        print(f"Exams (Secondary, by class): {sum(len(e) for e in exams_by_class.values())}")
        print(f"Total attempts: {len(plan)} (1 per student per exam in their class)")
        print()
        print("Score generation:")
        print(f"  - Distribution: Normal (mean={SCORE_MEAN}%, stdev={SCORE_STDEV}%)")
        print(f"  - Expected pass rate (~50%): ~68%")
        print(f"  - Range: {MIN_SCORE}-{MAX_SCORE}%")
        print()
        print("Sample attempts (first 15):")
        for i, (student_id, exam_id, _) in enumerate(plan[:15]):
            student = next(s for s in students if s.id == student_id)
            exam = next(e for e in exams if e.id == exam_id)
            print(f"  - {student.student_id} ({student.first_name} {student.last_name}) -> {exam.title}")
        if len(plan) > 15:
            print(f"  ... and {len(plan) - 15} more")
        print()
        print("Attempt defaults:")
        print(f"  - Status: GRADED (completed and marked)")
        print(f"  - Max score: 100")
        print(f"  - Submitted late: false")
        print()
        print("=" * 80)
        print()

        if not write_mode:
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create these attempts:")
            print()
            print(f'  python -m scripts.bootstrap_secondary_cbt_attempts "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print("Writing to database (this may take a moment for 1800 attempts)...")
        print()

        # Generate attempts with random scores
        rng = random.Random(42)  # Deterministic for reproducibility
        created_count = 0
        for student_id, exam_id, _ in plan:
            score = generate_realistic_score(rng)
            attempt = CBTAttempt(
                org_id=FAIRVIEW_ORG_ID,
                exam_id=exam_id,
                student_id=student_id,
                score=score,
                max_score=100.0,
                status=AttemptStatus.GRADED,
                submitted_late=False,
            )
            db.add(attempt)
            created_count += 1

        await db.commit()

        print(f"[OK] Created {created_count} CBT attempts successfully!")
        print()
        print(f"Sample attempts created:")
        for i, (student_id, exam_id, _) in enumerate(plan[:10]):
            student = next(s for s in students if s.id == student_id)
            exam = next(e for e in exams if e.id == exam_id)
            print(f"  [+] {student.student_id} ({student.first_name} {student.last_name}) -> {exam.title}")
        if len(plan) > 10:
            print(f"  ... and {len(plan) - 10} more")
        print()
        print("Next step: Run bootstrap_secondary_cbt_feed_gradebook.py to feed grades to the gradebook")
        print()

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
