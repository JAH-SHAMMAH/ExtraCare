"""
Verify that each school class's teacher_id matches the intended teacher
for its year group.

Usage:
    python -m scripts.verify_teacher_assignments "postgresql+asyncpg://user:pass@host/db?ssl=require"
"""
import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.verify_teacher_assignments <DATABASE_URL>")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User
from app.models.modules.platform import SchoolSection  # noqa: F401
from app.models.modules.school import SchoolClass


FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

EXPECTED = {
    "Early-Years": "amaka.okeke@fairviewschoolng.com",
    "Nursery": "ifeoma.nwachukwu@fairviewschoolng.com",
    "Reception": "blessing.adeyemi@fairviewschoolng.com",
    "Year 1": "grace.uzoma@fairviewschoolng.com",
    "Year 2": "emeka.obi@fairviewschoolng.com",
    "Year 3": "fatima.bello@fairviewschoolng.com",
    "Year 4": "chinedu.eze@fairviewschoolng.com",
    "Year 5": "halima.suleiman@fairviewschoolng.com",
    "Year 6": "tunde.adebayo@fairviewschoolng.com",
    "JSS1": "ngozi.chukwu@fairviewschoolng.com",
    "JSS2": "yakubu.musa@fairviewschoolng.com",
    "JSS3": "chiamaka.okafor@fairviewschoolng.com",
    "SSS1": "ibrahim.yusuf@fairviewschoolng.com",
    "SSS2": "adaeze.nnamdi@fairviewschoolng.com",
    "SSS3": "kunle.ogunleye@fairviewschoolng.com",
}


async def main():
    clean_url = sys.argv[1].split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        classes = (await db.execute(
            select(SchoolClass).where(SchoolClass.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        users = (await db.execute(
            select(User).where(User.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()
        user_by_id = {u.id: u.email for u in users}

        mismatches = []
        unassigned = []
        for c in sorted(classes, key=lambda x: x.name):
            expected_email = EXPECTED.get(c.level)
            actual_email = user_by_id.get(c.teacher_id) if c.teacher_id else None
            status = "OK" if actual_email == expected_email else "MISMATCH"
            if not actual_email:
                unassigned.append(c.name)
            elif actual_email != expected_email:
                mismatches.append((c.name, expected_email, actual_email))
            print(f"  {c.name:<16} teacher={actual_email or '(none)':<38} [{status}]")

        print()
        print(f"Total classes: {len(classes)}")
        print(f"Unassigned: {len(unassigned)}")
        print(f"Mismatched: {len(mismatches)}")
        if mismatches:
            print()
            for name, expected, actual in mismatches:
                print(f"  {name}: expected {expected}, got {actual}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
