"""
Backfill job_title on the 15 teacher accounts so the dashboard's teacher
count (which filters on job_title ILIKE '%teacher%') picks them up.

Usage (dry-run):
    python -m scripts.fix_teacher_job_titles "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.fix_teacher_job_titles "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.fix_teacher_job_titles <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User


FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

# (email, job_title)
JOB_TITLES = {
    "amaka.okeke@fairviewschoolng.com": "Early-Years Class Teacher",
    "ifeoma.nwachukwu@fairviewschoolng.com": "Nursery Class Teacher",
    "blessing.adeyemi@fairviewschoolng.com": "Reception Class Teacher",
    "grace.uzoma@fairviewschoolng.com": "Year 1 Class Teacher",
    "emeka.obi@fairviewschoolng.com": "Year 2 Class Teacher",
    "fatima.bello@fairviewschoolng.com": "Year 3 Class Teacher",
    "chinedu.eze@fairviewschoolng.com": "Year 4 Class Teacher",
    "halima.suleiman@fairviewschoolng.com": "Year 5 Class Teacher",
    "tunde.adebayo@fairviewschoolng.com": "Year 6 Class Teacher",
    "ngozi.chukwu@fairviewschoolng.com": "JSS1 Class Teacher",
    "yakubu.musa@fairviewschoolng.com": "JSS2 Class Teacher",
    "chiamaka.okafor@fairviewschoolng.com": "JSS3 Class Teacher",
    "ibrahim.yusuf@fairviewschoolng.com": "SSS1 Class Teacher",
    "adaeze.nnamdi@fairviewschoolng.com": "SSS2 Class Teacher",
    "kunle.ogunleye@fairviewschoolng.com": "SSS3 Class Teacher",
}


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        users = (await db.execute(
            select(User).where(
                User.org_id == FAIRVIEW_ORG_ID,
                User.email.in_(list(JOB_TITLES.keys())),
            )
        )).scalars().all()

        already_set = [u for u in users if u.job_title]
        if already_set:
            print(f"Found {len(already_set)} teachers that already have a job_title — nothing to do.")
            await engine.dispose()
            return 0

        print("=" * 70)
        print("DRY-RUN: The following job_title updates will be made:")
        print("=" * 70)
        print()
        for u in users:
            print(f"  {u.email:<40} -> {JOB_TITLES[u.email]}")
        print()
        print(f"Total: {len(users)} accounts")
        print()
        print("=" * 70)

        if not write_mode:
            print()
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually update:")
            print()
            print(f'  python -m scripts.fix_teacher_job_titles "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print()
        print("Writing to database...")
        print()

        for u in users:
            u.job_title = JOB_TITLES[u.email]

        await db.commit()

        print(f"✓ {len(users)} teacher job_titles updated successfully!")
        print()
        print("Dashboard teacher count should now show 15.")

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
