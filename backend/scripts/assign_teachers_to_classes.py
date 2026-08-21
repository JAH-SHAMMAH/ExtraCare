"""
Assign each of the 15 teachers to both streams (A/B) of their matching
year group's school classes.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.assign_teachers_to_classes "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.assign_teachers_to_classes "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.assign_teachers_to_classes <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User
from app.models.modules.platform import SchoolSection  # noqa: F401 — registers FK target table
from app.models.modules.school import SchoolClass


FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

# (year_group_level, teacher_email)
YEAR_GROUP_TO_TEACHER_EMAIL = {
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


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        classes = (await db.execute(
            select(SchoolClass).where(SchoolClass.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        teachers = (await db.execute(
            select(User).where(
                User.org_id == FAIRVIEW_ORG_ID,
                User.email.in_(list(YEAR_GROUP_TO_TEACHER_EMAIL.values())),
            )
        )).scalars().all()
        teacher_by_email = {t.email: t for t in teachers}

        already_assigned = [c for c in classes if c.teacher_id is not None]
        if already_assigned:
            print(f"Found {len(already_assigned)} classes that already have a teacher assigned — nothing to do.")
            await engine.dispose()
            return 0

        plan = []  # (class_name, class_id, teacher_email, teacher_id)
        unmatched = []
        for c in classes:
            teacher_email = YEAR_GROUP_TO_TEACHER_EMAIL.get(c.level)
            teacher = teacher_by_email.get(teacher_email) if teacher_email else None
            if not teacher:
                unmatched.append(c.name)
                continue
            plan.append((c.name, c.id, teacher_email, teacher.id))

        print("=" * 70)
        print("DRY-RUN: The following teacher assignments will be made:")
        print("=" * 70)
        print()
        for class_name, _, teacher_email, _ in plan:
            print(f"  {class_name:<16} -> {teacher_email}")
        print()
        print(f"Total: {len(plan)} class assignments")
        if unmatched:
            print(f"\nUnmatched classes (no teacher found for level): {', '.join(unmatched)}")
        print()
        print("=" * 70)

        if not write_mode:
            print()
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually assign teachers:")
            print()
            print(f'  python -m scripts.assign_teachers_to_classes "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print()
        print("Writing to database...")
        print()

        class_by_id = {c.id: c for c in classes}
        for class_name, class_id, teacher_email, teacher_id in plan:
            class_by_id[class_id].teacher_id = teacher_id

        await db.commit()

        print(f"✓ {len(plan)} class-teacher assignments completed successfully!")
        print()
        print("Next step: Create student accounts")

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
