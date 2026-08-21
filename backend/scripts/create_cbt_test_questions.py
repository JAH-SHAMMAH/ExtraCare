#!/usr/bin/env python
"""Create test questions for a specific CBT exam."""

import asyncio
import sys
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import CBTExam, CBTQuestion, QuestionType

DB_URL = "postgresql+asyncpg://fairview_data_user:1MMCmx2rVy0XbXNh1IBjclMiOH1ACPVa@dpg-da243tn40ujc7394oip0-a.ohio-postgres.render.com/fairview_data?ssl=require"

async def main():
    clean_url = DB_URL.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"}, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        exam_id = "25ef7e84-726c-4308-adbd-40de2e0875c1"
        exam = await db.get(CBTExam, exam_id)

        if not exam:
            print(f"[ERROR] Exam {exam_id} not found")
            await engine.dispose()
            return

        print(f"[OK] Found exam: {exam.title}")

        # Check existing questions
        existing = (await db.execute(
            select(CBTQuestion).where(CBTQuestion.exam_id == exam_id)
        )).scalars().all()

        if existing:
            print(f"[WARNING] Exam already has {len(existing)} questions. Skipping.")
            await engine.dispose()
            return

        # Create 5 test questions
        questions_data = [
            {
                "text": "What is the basic structural and functional unit of life?",
                "type": QuestionType.MCQ,
                "options": ["Cell", "Atom", "Molecule", "Tissue"],
                "correct": "Cell"
            },
            {
                "text": "Photosynthesis occurs primarily in which organelle?",
                "type": QuestionType.MCQ,
                "options": ["Mitochondria", "Chloroplast", "Ribosome", "Nucleus"],
                "correct": "Chloroplast"
            },
            {
                "text": "DNA is the genetic material in all living organisms.",
                "type": QuestionType.TRUE_FALSE,
                "options": ["True", "False"],
                "correct": "False"
            },
            {
                "text": "Respiration is the process by which organisms produce energy.",
                "type": QuestionType.TRUE_FALSE,
                "options": ["True", "False"],
                "correct": "True"
            },
            {
                "text": "Which blood type is known as the universal donor?",
                "type": QuestionType.MCQ,
                "options": ["A", "B", "AB", "O-negative"],
                "correct": "O-negative"
            },
        ]

        for i, q_data in enumerate(questions_data, 1):
            question = CBTQuestion(
                id=str(uuid4()),
                org_id=exam.org_id,
                exam_id=exam_id,
                question_text=q_data["text"],
                question_type=q_data["type"],
                correct_answer=q_data["correct"],
                options=q_data["options"],
                position=i,
            )
            db.add(question)

        await db.commit()
        print(f"\n[OK] Created 5 Biology questions:")
        print(f"  - 3 Multiple Choice")
        print(f"  - 2 True/False")
        print(f"\nExam {exam.id} is ready for students to take")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
