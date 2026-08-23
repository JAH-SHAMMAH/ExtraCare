#!/usr/bin/env python
"""
DRY-RUN: Count actual CBT Grade records that will be backfilled to StudentAssessmentScore.

Shows REAL numbers from the database, not predictions.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

from app.models.modules.school import Grade

DB_URL = "postgresql+asyncpg://fairview_data_user:1MMCmx2rVy0XbXNh1IBjclMiOH1ACPVa@dpg-da243tn40ujc7394oip0-a.ohio-postgres.render.com/fairview_data?ssl=require"
FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"


async def dry_run():
    clean_url = DB_URL.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"}, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("DRY-RUN: CBT to StudentAssessmentScore backfill")
        print("=" * 80)
        print()

        # Count Grade records where cbt_exam_id IS NOT NULL (CBT-sourced)
        cbt_grades = (await db.execute(
            select(Grade).where(
                Grade.org_id == FAIRVIEW_ORG_ID,
                Grade.cbt_exam_id.isnot(None)
            )
        )).scalars().all()

        print(f"Total Grade records (cbt_exam_id IS NOT NULL): {len(cbt_grades)}")
        print()

        # Group by student_id, subject_id to get unique (student, subject) pairs
        pairs = set()
        for grade in cbt_grades:
            pairs.add((grade.student_id, grade.subject_id))

        print(f"Unique (student_id, subject_id) pairs: {len(pairs)}")
        print()

        # Show breakdown by student
        student_counts = {}
        for student_id, subject_id in pairs:
            student_counts[student_id] = student_counts.get(student_id, 0) + 1

        print(f"Students with grades: {len(student_counts)}")
        if student_counts:
            avg_subjects = sum(student_counts.values()) / len(student_counts)
            print(f"Average subjects per student: {avg_subjects:.1f}")
            print(f"Min subjects per student: {min(student_counts.values())}")
            print(f"Max subjects per student: {max(student_counts.values())}")
        print()

        print(f"[RESULT] Will create {len(pairs)} StudentAssessmentScore rows")
        print()

        # Show sample of grades (first 5 pairs)
        if pairs:
            print("Sample pairs (first 5):")
            for i, (sid, subj_id) in enumerate(list(pairs)[:5], 1):
                grade_obj = next(g for g in cbt_grades if g.student_id == sid and g.subject_id == subj_id)
                print(f"  {i}. Student {sid[:8]}... Subject {subj_id[:8]}... Score: {grade_obj.score}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(dry_run())
