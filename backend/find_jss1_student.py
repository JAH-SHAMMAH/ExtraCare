#!/usr/bin/env python
"""Find a JSS1 Secondary student with at least one exam available."""

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.user import User
from app.models.modules.school import Student, SchoolClass, CBTExam, CBTAttempt, ExamStatus
from app.models.modules.platform import SchoolSection

DB_URL = "postgresql+asyncpg://fairview_data_user:1MMCmx2rVy0XbXNh1IBjclMiOH1ACPVa@dpg-da243tn40ujc7394oip0-a.ohio-postgres.render.com/fairview_data?ssl=require"
FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

async def main():
    clean_url = DB_URL.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        # Find JSS1 A class (Secondary section)
        jss1_class = (await db.execute(
            select(SchoolClass).where(
                SchoolClass.org_id == FAIRVIEW_ORG_ID,
                SchoolClass.name == "JSS1 A"
            )
        )).scalars().first()

        if not jss1_class:
            print("[ERROR] JSS1 class not found")
            await engine.dispose()
            return

        print(f"\n[OK] Found JSS1 class: {jss1_class.id}")

        # Get section
        section = await db.get(SchoolSection, jss1_class.section_id)
        print(f"[OK] Section: {section.name}")

        # Find first student in JSS1
        student = (await db.execute(
            select(Student).where(
                Student.org_id == FAIRVIEW_ORG_ID,
                Student.class_id == jss1_class.id,
            ).order_by(Student.student_id)
        )).scalars().first()

        if not student:
            print("[ERROR] No students in JSS1")
            await engine.dispose()
            return

        print(f"[OK] Student: {student.student_id} (id: {student.id})")

        # Get their user account
        user = await db.get(User, student.user_id)
        if not user:
            print("[ERROR] Student has no user account")
            await engine.dispose()
            return

        print(f"[OK] Email: {user.email}")

        # Find an exam for this student's class that they have NOT yet taken
        exams = (await db.execute(
            select(CBTExam).where(
                CBTExam.org_id == FAIRVIEW_ORG_ID,
                CBTExam.class_id == jss1_class.id,
                CBTExam.is_deleted == False,
                CBTExam.status.in_([ExamStatus.PUBLISHED, ExamStatus.ACTIVE])
            ).order_by(CBTExam.created_at)
        )).scalars().all()

        print(f"\n[OK] Found {len(exams)} exams for JSS1")

        # For each exam, check if student already has an attempt
        available_exam = None
        for exam in exams[:5]:
            attempt = (await db.execute(
                select(CBTAttempt).where(
                    CBTAttempt.student_id == student.id,
                    CBTAttempt.exam_id == exam.id
                )
            )).scalar_one_or_none()

            status = "✓ ALREADY ATTEMPTED" if attempt else "○ Available"
            print(f"  - {exam.name}: {status}")

            if not attempt and not available_exam:
                available_exam = exam

        if available_exam:
            print(f"\n[OK] Student can take: {available_exam.name}")
        else:
            print("\n[WARNING] Student has attempted all exams. Creating fresh test exam...")

            # Use first exam's subject if available
            subject_id = None
            if exams:
                subject_id = exams[0].subject_id

            test_exam = CBTExam(
                id=str(uuid4()),
                org_id=FAIRVIEW_ORG_ID,
                class_id=jss1_class.id,
                subject_id=subject_id,
                name="[TEST] Fresh Exam - Live Testing",
                description="Temporary exam for end-to-end CBT testing",
                question_count=5,
                max_score=50,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(days=1),
                status=ExamStatus.PUBLISHED,
                is_deleted=False,
                created_by=None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(test_exam)
            await db.flush()
            available_exam = test_exam
            print(f"[OK] Created fresh exam")

        print(f"\n{'='*80}")
        print(f"LIVE CBT TEST — STUDENT CREDENTIALS")
        print(f"{'='*80}")
        print(f"Email:    {user.email}")
        print(f"Password: (from student_credentials_output.csv line 2)")
        print(f"Exam:     {available_exam.name}")
        print(f"URL:      https://youromain/dashboard/my-exams")
        print(f"{'='*80}\n")

        await db.commit()

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
