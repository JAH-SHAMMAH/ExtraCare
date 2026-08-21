"""
Bootstrap 15 teacher accounts for Fairview School — one per year group.
Names are synthetic placeholders (not real staff) but realistic, so
records read cleanly. Update to actual staff details when available.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_teachers "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_teachers "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_teachers <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User, UserStatus
from app.models.role import Role
from app.core.security import hash_password, generate_secure_token


FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

# (year_group_label, full_name, email_local_part)
TEACHERS = [
    ("Early-Years", "Amaka Okeke", "amaka.okeke"),
    ("Nursery", "Ifeoma Nwachukwu", "ifeoma.nwachukwu"),
    ("Reception", "Blessing Adeyemi", "blessing.adeyemi"),
    ("Year 1", "Grace Uzoma", "grace.uzoma"),
    ("Year 2", "Emeka Obi", "emeka.obi"),
    ("Year 3", "Fatima Bello", "fatima.bello"),
    ("Year 4", "Chinedu Eze", "chinedu.eze"),
    ("Year 5", "Halima Suleiman", "halima.suleiman"),
    ("Year 6", "Tunde Adebayo", "tunde.adebayo"),
    ("JSS1", "Ngozi Chukwu", "ngozi.chukwu"),
    ("JSS2", "Yakubu Musa", "yakubu.musa"),
    ("JSS3", "Chiamaka Okafor", "chiamaka.okafor"),
    ("SSS1", "Ibrahim Yusuf", "ibrahim.yusuf"),
    ("SSS2", "Adaeze Nnamdi", "adaeze.nnamdi"),
    ("SSS3", "Kunle Ogunleye", "kunle.ogunleye"),
]


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        teacher_role = (await db.execute(
            select(Role).where(Role.org_id == FAIRVIEW_ORG_ID, Role.slug == "teacher")
        )).scalar_one_or_none()

        if not teacher_role:
            print("ERROR: teacher role not found for this org.")
            print("This should have been created by bootstrap_fairview_org.py.")
            await engine.dispose()
            return 1

        existing = (await db.execute(
            select(User).where(
                User.org_id == FAIRVIEW_ORG_ID,
                User.email.like("%@fairviewschoolng.com"),
                User.email != "director@fairviewschoolng.com",
            )
        )).scalars().all()

        if existing:
            print(f"Found {len(existing)} existing non-director staff accounts — nothing to do.")
            for u in existing:
                print(f"  - {u.email}")
            await engine.dispose()
            return 0

        plan = []
        for year_group, full_name, local_part in TEACHERS:
            email = f"{local_part}@fairviewschoolng.com"
            temp_password = generate_secure_token(length=16)
            plan.append((year_group, full_name, email, temp_password))

        print("=" * 70)
        print("DRY-RUN: The following 15 teacher accounts will be created:")
        print("=" * 70)
        print()
        for year_group, full_name, email, temp_password in plan:
            print(f"  {year_group:<12} {full_name:<20} {email:<32} pw: {temp_password}")
        print()
        print("All accounts: role=teacher, status=active, force_password_change=true")
        print()
        print("=" * 70)

        if not write_mode:
            print()
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create these accounts:")
            print()
            print(f'  python -m scripts.bootstrap_teachers "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print()
        print("Writing to database...")
        print()

        for year_group, full_name, email, temp_password in plan:
            hashed = hash_password(temp_password)
            user = User(
                email=email.lower(),
                full_name=full_name,
                hashed_password=hashed,
                status=UserStatus.ACTIVE,
                org_id=FAIRVIEW_ORG_ID,
                force_password_change=True,
                email_verified=False,
            )
            user.roles = [teacher_role]
            db.add(user)

        await db.flush()
        await db.commit()

        print(f"✓ {len(plan)} teacher accounts created successfully!")
        print()
        print("Login credentials (SAVE THESE — shown once):")
        print()
        for year_group, full_name, email, temp_password in plan:
            print(f"  {year_group:<12} {email:<32} pw: {temp_password}")
        print()
        print("Next step: Assign teacher_id to each of the 30 school classes")

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
