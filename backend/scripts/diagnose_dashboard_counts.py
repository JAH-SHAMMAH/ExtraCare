"""
Replicate the dashboard's exact student/teacher count queries directly,
to see what the numbers actually are and why they might show as zero.

Usage:
    python -m scripts.diagnose_dashboard_counts "postgresql+asyncpg://user:pass@host/db?ssl=require"
"""
import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.diagnose_dashboard_counts <DATABASE_URL>")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User
from app.models.modules.school import Student


FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"


async def main():
    clean_url = sys.argv[1].split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Exact dashboard student query
        student_rows = (await db.execute(
            select(func.lower(Student.gender), func.count(Student.id))
            .where(
                Student.org_id == FAIRVIEW_ORG_ID,
                Student.is_deleted == False,
                Student.is_active == True,
            )
            .group_by(func.lower(Student.gender))
        )).all()
        print("Dashboard student query result:")
        for gender, count in student_rows:
            print(f"  {gender}: {count}")
        if not student_rows:
            print("  (empty — 0 students match the filter)")

        # Raw counts without filters, for comparison
        total_students = (await db.execute(
            select(func.count(Student.id)).where(Student.org_id == FAIRVIEW_ORG_ID)
        )).scalar_one()
        active_students = (await db.execute(
            select(func.count(Student.id)).where(
                Student.org_id == FAIRVIEW_ORG_ID, Student.is_active == True
            )
        )).scalar_one()
        not_deleted_students = (await db.execute(
            select(func.count(Student.id)).where(
                Student.org_id == FAIRVIEW_ORG_ID, Student.is_deleted == False
            )
        )).scalar_one()
        null_is_deleted = (await db.execute(
            select(func.count(Student.id)).where(
                Student.org_id == FAIRVIEW_ORG_ID, Student.is_deleted.is_(None)
            )
        )).scalar_one()

        print()
        print(f"Total students (org, no filter): {total_students}")
        print(f"  is_active=True: {active_students}")
        print(f"  is_deleted=False: {not_deleted_students}")
        print(f"  is_deleted IS NULL: {null_is_deleted}")

        # Exact dashboard teacher query
        teachers_count = (await db.execute(
            select(func.count(User.id)).where(
                User.org_id == FAIRVIEW_ORG_ID,
                User.is_deleted == False,
                User.job_title.ilike("%teacher%"),
            )
        )).scalar_one() or 0
        print()
        print(f"Dashboard teacher query result: {teachers_count}")

        # Check what job_title actually is for our teacher accounts
        sample = (await db.execute(
            select(User.email, User.job_title, User.is_deleted).where(
                User.org_id == FAIRVIEW_ORG_ID,
                User.email.like("%@fairviewschoolng.com"),
                User.email != "director@fairviewschoolng.com",
            ).limit(5)
        )).all()
        print()
        print("Sample teacher accounts (email, job_title, is_deleted):")
        for email, job_title, is_deleted in sample:
            print(f"  {email:<35} job_title={job_title!r:<15} is_deleted={is_deleted}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
