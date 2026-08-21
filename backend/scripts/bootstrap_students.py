"""
Bootstrap 450 student records + login accounts for Fairview School:
15 students per class across all 30 school classes. Names are synthetic
(Nigerian name pools) but realistic; ages roughly match year group.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_students "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_students "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os
import random
from datetime import date

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_students <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.platform import SchoolSection  # noqa: F401 — registers FK target table
from app.models.modules.school import SchoolClass, Student
from app.core.security import hash_password, generate_secure_token


FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"
STUDENTS_PER_CLASS = 15
ADMISSION_DATE = date(2025, 9, 15)

# Approx age per year group level, used to compute a rough date_of_birth.
LEVEL_TO_AGE = {
    "Early-Years": 2, "Nursery": 3, "Reception": 4,
    "Year 1": 5, "Year 2": 6, "Year 3": 7, "Year 4": 8, "Year 5": 9, "Year 6": 10,
    "JSS1": 11, "JSS2": 12, "JSS3": 13,
    "SSS1": 14, "SSS2": 15, "SSS3": 16,
}

MALE_FIRST_NAMES = [
    "Chinedu", "Emeka", "Tunde", "Yakubu", "Ibrahim", "Kunle", "Segun", "Femi",
    "Obinna", "Chukwudi", "Musa", "Aliyu", "Damilare", "Uche", "Kelechi",
    "Ayodele", "Chibuike", "Suleiman", "Olumide", "Ikenna",
]
FEMALE_FIRST_NAMES = [
    "Amaka", "Ifeoma", "Blessing", "Grace", "Fatima", "Halima", "Ngozi",
    "Chiamaka", "Adaeze", "Bimpe", "Funke", "Chidinma", "Aisha", "Zainab",
    "Ronke", "Adaora", "Nkechi", "Yetunde", "Ndidi", "Rukayat",
]
LAST_NAMES = [
    "Okeke", "Nwachukwu", "Adeyemi", "Uzoma", "Obi", "Bello", "Eze", "Suleiman",
    "Adebayo", "Chukwu", "Musa", "Okafor", "Yusuf", "Nnamdi", "Ogunleye",
    "Ibrahim", "Okonkwo", "Balogun", "Abubakar", "Ojo", "Nwosu", "Danjuma",
    "Adeleke", "Okoro", "Sani", "Umeh", "Bakare", "Ezenwa", "Lawal", "Chukwuemeka",
]


def generate_name(rng: random.Random) -> tuple[str, str, str]:
    """Returns (first_name, last_name, gender)."""
    gender = rng.choice(["M", "F"])
    first = rng.choice(MALE_FIRST_NAMES if gender == "M" else FEMALE_FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    return first, last, gender


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        student_role = (await db.execute(
            select(Role).where(Role.org_id == FAIRVIEW_ORG_ID, Role.slug == "student")
        )).scalar_one_or_none()

        if not student_role:
            print("ERROR: student role not found for this org.")
            await engine.dispose()
            return 1

        classes = (await db.execute(
            select(SchoolClass).where(SchoolClass.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if not classes:
            print("ERROR: No school classes found. Run bootstrap_school_classes.py first.")
            await engine.dispose()
            return 1

        existing = (await db.execute(
            select(Student).where(Student.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if existing:
            print(f"Found {len(existing)} existing student records — nothing to do.")
            await engine.dispose()
            return 0

        # Build the plan deterministically (fixed seed so dry-run == write)
        rng = random.Random(42)
        plan = []  # (student_id, first, last, gender, dob, class_id, class_name, email, temp_password)
        seq = 1
        for c in sorted(classes, key=lambda x: x.name):
            age = LEVEL_TO_AGE.get(c.level, 10)
            dob = date(ADMISSION_DATE.year - age, 1, 1)
            for _ in range(STUDENTS_PER_CLASS):
                first, last, gender = generate_name(rng)
                student_id = f"FSN-{seq:04d}"
                email = f"{first.lower()}.{last.lower()}{seq:04d}@fairviewschoolng.com"
                temp_password = generate_secure_token(length=16)
                plan.append((student_id, first, last, gender, dob, c.id, c.name, email, temp_password))
                seq += 1

        print("=" * 70)
        print(f"DRY-RUN: {len(plan)} students will be created ({STUDENTS_PER_CLASS} per class x {len(classes)} classes)")
        print("=" * 70)
        print()
        for student_id, first, last, gender, dob, class_id, class_name, email, temp_password in plan[:10]:
            print(f"  {student_id}  {first} {last:<12} ({gender})  {class_name:<16} {email}")
        print(f"  ... and {len(plan) - 10} more")
        print()
        print("Each student gets: enrollment record + login account (role=student, force_password_change=true)")
        print()
        print("=" * 70)

        if not write_mode:
            print()
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create these records:")
            print()
            print(f'  python -m scripts.bootstrap_students "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print()
        print("Writing to database (this may take a moment for 450 records)...")
        print()

        credentials_log = []
        user_objs = []
        for student_id, first, last, gender, dob, class_id, class_name, email, temp_password in plan:
            hashed = hash_password(temp_password)
            user = User(
                email=email.lower(),
                full_name=f"{first} {last}",
                hashed_password=hashed,
                status=UserStatus.ACTIVE,
                org_id=FAIRVIEW_ORG_ID,
                force_password_change=True,
                email_verified=False,
            )
            user.roles = [student_role]
            db.add(user)
            user_objs.append(user)
            credentials_log.append((student_id, email, temp_password))

        # Flush to generate user IDs before creating Student rows that reference them
        await db.flush()

        for (student_id, first, last, gender, dob, class_id, class_name, email, temp_password), user in zip(plan, user_objs):
            db.add(Student(
                org_id=FAIRVIEW_ORG_ID,
                student_id=student_id,
                first_name=first,
                last_name=last,
                email=email.lower(),
                date_of_birth=dob,
                gender=gender,
                user_id=user.id,
                class_id=class_id,
                admission_date=ADMISSION_DATE,
                is_active=True,
            ))

        await db.commit()

        print(f"✓ {len(plan)} students created successfully (enrollment + login)!")
        print()

        # Write full credentials to a local file rather than flooding the terminal
        out_path = os.path.join(os.path.dirname(__file__), "student_credentials_output.csv")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("student_id,email,temp_password\n")
            for student_id, email, temp_password in credentials_log:
                f.write(f"{student_id},{email},{temp_password}\n")

        print(f"Full credentials (450 rows) written to: {out_path}")
        print("This file contains plaintext passwords — store it securely and delete after distributing.")
        print()
        print("Next step: create real teacher/student records to replace placeholders, or move on to other modules.")

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
