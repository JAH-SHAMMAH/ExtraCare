#!/usr/bin/env python3
"""
CREATE STUDENT LOGIN ACCOUNT (Real write)

This script actually creates a user account for a student and sets a password.
THE PASSWORD IS PRINTED TO TERMINAL ONLY — NEVER STORED OR COMMITTED.

IMPORTANT: Run the dry-run first to verify which student you're targeting:
  python scripts/create_student_login_dryrun.py "email@..."

Then run this script:
  python scripts/create_student_login_real.py "email@..."

Usage:
  python scripts/create_student_login_real.py <student_email>

Example:
  python scripts/create_student_login_real.py "zainab.obi@student.fairview-school.ng"
"""

from __future__ import annotations

import asyncio
import sys
import secrets
import string

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, init_db
from app.models.user import User
from app.models.role import Role
from app.models.student import Student
from passlib.context import CryptContext

# Password hashing (same as app/core/auth.py)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/create_student_login_real.py <student_email>")
        return 2

    student_email = sys.argv[1].strip().lower()

    await init_db()

    async with AsyncSessionLocal() as db:
        # 1. Find the student
        student = (await db.execute(
            select(Student).where(Student.email.ilike(student_email), Student.org_id)
        )).scalar_one_or_none()

        if not student:
            print(f"ERROR: No student found with email '{student_email}'.")
            return 1

        if student.user_id:
            print(f"ERROR: Student already has a user account (user_id={student.user_id}).")
            return 1

        # 2. Verify Student role exists
        student_role = (await db.execute(
            select(Role).where(Role.org_id == student.org_id, Role.slug == "student")
        )).scalar_one_or_none()

        if not student_role:
            print(f"ERROR: 'student' role not found in org {student.org_id}.")
            print("       This should have been created during app bootstrap.")
            return 1

        # 3. Generate a secure random password
        password_chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(password_chars) for _ in range(16))
        hashed = pwd_context.hash(password)

        # 4. Create the user account
        user = User(
            email=student_email,
            full_name=f"{student.first_name} {student.last_name}".strip(),
            hashed_password=hashed,
            org_id=student.org_id,
            is_active=True,
        )
        user.roles = [student_role]
        db.add(user)
        await db.flush()

        # 5. Link student to user
        student.user_id = user.id
        await db.flush()

        # 6. Commit
        await db.commit()

        # 7. Print results (password ONLY printed to terminal, never stored)
        print("\n" + "="*100)
        print("STUDENT ACCOUNT CREATED SUCCESSFULLY")
        print("="*100)
        print(f"\nStudent: {student.first_name} {student.last_name}")
        print(f"Email:   {student_email}")
        print(f"Class:   {student.student_id}")
        print(f"\nLogin credentials:")
        print(f"  Email:    {student_email}")
        print(f"  Password: {password}")
        print(f"\n** IMPORTANT **")
        print(f"  The password above is shown ONLY now, in your terminal.")
        print(f"  It is NEVER stored in git, logs, or any file.")
        print(f"  Share it with the student securely (SMS, in-person, parent email, etc.)")
        print(f"  The student can change it after first login.")
        print("\n" + "="*100 + "\n")

        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
