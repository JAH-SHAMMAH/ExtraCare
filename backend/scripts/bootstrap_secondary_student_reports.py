"""
Bootstrap StudentReport metadata for Fairview Secondary students.

Creates one StudentReport row per Secondary student per term, containing
metadata that isn't derivable from grades: class_teacher_comment,
head_teacher_comment, attendance_present, attendance_total, etc.

This populates the non-grade fields of the report card (comments, attendance
counts) so the report card renders complete without manual entry.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_secondary_student_reports "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_secondary_student_reports "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os
import random

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_secondary_student_reports <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import Student, StudentReport
from app.models.modules.platform import AcademicTerm

FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"
CURRENT_TERM = "Term 1"

# Attendance defaults: assume 85% average attendance across all students
SCHOOL_DAYS = 60  # Typical term school days
ATTENDANCE_RATE = 0.85


def generate_attendance(rng: random.Random) -> tuple[int, int]:
    """Generate realistic attendance counts (present, total)."""
    total = SCHOOL_DAYS
    # Normal distribution around 85%, with stdev of 5%
    attendance_pct = rng.gauss(ATTENDANCE_RATE * 100, 5)
    attendance_pct = max(0, min(100, attendance_pct))  # Clamp to 0-100
    present = int(total * attendance_pct / 100)
    return present, total


def generate_comment(rng: random.Random, name: str, is_head: bool = False) -> str:
    """Generate a realistic teacher comment."""
    if is_head:
        templates = [
            f"{name} has shown excellent academic progress this term.",
            f"{name} demonstrates strong potential. Continue to build on this foundation.",
            f"{name} is a dedicated learner. Good performance across subjects.",
            f"{name}'s work ethic and commitment are commendable.",
            f"{name} shows promise and should maintain current level of effort.",
        ]
    else:
        templates = [
            f"{name} is progressing well in class.",
            f"{name} demonstrates good understanding of class concepts.",
            f"{name} participates actively in lessons.",
            f"{name}'s assignments show consistent effort.",
            f"{name} could benefit from more engagement with challenging material.",
        ]
    return rng.choice(templates)


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    # Create async engine with proper SSL handling
    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Fetch Secondary students only
        secondary_levels = ["JSS1", "JSS2", "JSS3", "SSS1", "SSS2", "SSS3"]
        from app.models.modules.school import SchoolClass

        secondary_classes = (await db.execute(
            select(SchoolClass).where(
                SchoolClass.org_id == FAIRVIEW_ORG_ID,
                SchoolClass.level.in_(secondary_levels)
            )
        )).scalars().all()

        class_ids = [c.id for c in secondary_classes]

        students = (await db.execute(
            select(Student).where(
                Student.org_id == FAIRVIEW_ORG_ID,
                Student.class_id.in_(class_ids)
            )
        )).scalars().all()

        if not students:
            print("ERROR: No Secondary students found.")
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
            print(f"ERROR: Academic term '{CURRENT_TERM}' not found.")
            await engine.dispose()
            return 1

        # Check for existing StudentReport records (idempotent)
        existing = (await db.execute(
            select(StudentReport).where(StudentReport.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if len(existing) >= len(students):
            print(f"Found {len(existing)} existing StudentReport records — nothing to do.")
            await engine.dispose()
            return 0

        print("=" * 80)
        print(f"DRY-RUN: StudentReport metadata will be created for {len(students)} Secondary students")
        print("=" * 80)
        print()
        print(f"Students: {len(students)} (JSS1-3, SSS1-3)")
        print(f"Term: {CURRENT_TERM}")
        print()
        print("Fields per report:")
        print(f"  - Class teacher comment (realistic generated text)")
        print(f"  - Head teacher comment (realistic generated text)")
        print(f"  - Attendance: present/total days (distribution: mean={ATTENDANCE_RATE*100}%, σ=5%)")
        print(f"  - School days per term: {SCHOOL_DAYS}")
        print()
        print("Sample reports to create:")
        for student in students[:10]:
            print(f"  - {student.student_id} ({student.first_name} {student.last_name})")
        if len(students) > 10:
            print(f"  ... and {len(students) - 10} more")
        print()
        print("Expected result:")
        print(f"  - {len(students)} StudentReport records created")
        print(f"  - All fields populated (comments + attendance)")
        print(f"  - Report cards render complete metadata")
        print()
        print("=" * 80)
        print()

        if not write_mode:
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create these reports:")
            print()
            print(f'  python -m scripts.bootstrap_secondary_student_reports "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print("Writing to database...")
        print()

        rng = random.Random(42)  # Deterministic for reproducibility
        created_count = 0

        for student in students:
            # Skip if report already exists for this student+term
            existing_report = (await db.execute(
                select(StudentReport).where(
                    StudentReport.student_id == student.id,
                    StudentReport.term == CURRENT_TERM
                )
            )).scalar_one_or_none()

            if existing_report:
                continue

            present, total = generate_attendance(rng)
            class_teacher_comment = generate_comment(rng, student.first_name, is_head=False)
            head_teacher_comment = generate_comment(rng, student.first_name, is_head=True)

            report = StudentReport(
                org_id=FAIRVIEW_ORG_ID,
                student_id=student.id,
                term=CURRENT_TERM,
                class_teacher_comment=class_teacher_comment,
                head_teacher_comment=head_teacher_comment,
                attendance_present=present,
                attendance_total=total,
            )
            db.add(report)
            created_count += 1

        await db.commit()

        print(f"[OK] Created {created_count} StudentReport records!")
        print()
        print(f"Sample reports created:")
        for student in students[:10]:
            print(f"  [+] {student.student_id} ({student.first_name} {student.last_name})")
        if len(students) > 10:
            print(f"  ... and {len(students) - 10} more")
        print()
        print(f"Attendance stats (expected):")
        print(f"  - Mean attendance: {ATTENDANCE_RATE*100:.0f}%")
        print(f"  - Days per term: {SCHOOL_DAYS}")
        print()
        print("Next step: Layer 7 creates Non-Assessment Comments tab entries")
        print()

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
