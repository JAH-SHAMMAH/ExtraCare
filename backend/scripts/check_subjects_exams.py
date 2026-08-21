"""
Check whether Subject, CBTExam, GradingScale rows exist for Fairview.

Usage:
    python -m scripts.check_subjects_exams "postgresql+asyncpg://user:pass@host/db?ssl=require"
"""
import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.check_subjects_exams <DATABASE_URL>")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import Subject, CBTExam, Grade
from app.models.modules.platform import GradingScale, AssessmentDomain


FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"


async def main():
    clean_url = sys.argv[1].split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        for label, model in [
            ("Subjects", Subject),
            ("CBTExams", CBTExam),
            ("Grades", Grade),
            ("GradingScales", GradingScale),
            ("AssessmentDomains", AssessmentDomain),
        ]:
            count = (await db.execute(
                select(func.count(model.id)).where(model.org_id == FAIRVIEW_ORG_ID)
            )).scalar_one()
            print(f"{label}: {count}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
