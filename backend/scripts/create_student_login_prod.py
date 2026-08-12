#!/usr/bin/env python3
"""
Create student login account in PRODUCTION Postgres database.

Usage:
  python scripts/create_student_login_prod.py "email@fairviewschoolng.com" "postgresql://user:pass@host/db"

Example:
  python scripts/create_student_login_prod.py "abebi.abioye@fairviewschoolng.com" \
    "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz"

The password is printed to terminal ONLY — never stored in git or any file.
"""

import sys
import asyncio
import secrets
import string
from datetime import datetime
import bcrypt

async def main():
    if len(sys.argv) < 3:
        print("usage: python scripts/create_student_login_prod.py <email> <postgresql_url>")
        print("")
        print("Example:")
        print("  python scripts/create_student_login_prod.py abebi.abioye@fairviewschoolng.com \\")
        print("    'postgresql://user:pass@host/db'")
        return 2

    student_email = sys.argv[1].strip().lower()
    database_url = sys.argv[2].strip()

    try:
        import asyncpg
    except ImportError:
        print("[ERROR] asyncpg not installed. Run: pip install asyncpg")
        return 1

    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return 1

    try:
        # Find the student
        student = await conn.fetchrow(
            "SELECT id, first_name, last_name, email FROM students WHERE LOWER(email) = $1",
            student_email
        )

        if not student:
            print(f"[ERROR] Student not found: {student_email}")
            return 1

        student_id = student['id']

        # Check if student already has a user account
        existing_user = await conn.fetchval(
            "SELECT id FROM users WHERE id = (SELECT user_id FROM students WHERE id = $1)",
            student_id
        )

        if existing_user:
            print(f"[ERROR] Student already has a user account: {student_email}")
            return 1

        # Get organisation
        org_id = await conn.fetchval(
            "SELECT org_id FROM students WHERE id = $1",
            student_id
        )

        if not org_id:
            print(f"[ERROR] Student has no organisation assigned")
            return 1

        # Get student role
        student_role_id = await conn.fetchval(
            "SELECT id FROM roles WHERE org_id = $1 AND slug = 'student'",
            org_id
        )

        if not student_role_id:
            print(f"[ERROR] Student role not found in organisation")
            return 1

        # Generate password and hash with bcrypt
        password = ''.join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*()") for _ in range(16))
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode(), salt).decode()

        # Create user account
        now = datetime.utcnow().isoformat()
        user_id = secrets.token_hex(8)

        async with conn.transaction():
            # Insert user
            await conn.execute(
                """
                INSERT INTO users (
                    id, org_id, email, full_name, hashed_password,
                    status, email_verified, is_deleted, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                user_id, org_id, student_email,
                f"{student['first_name']} {student['last_name']}",
                hashed,
                'active', True, False, now, now
            )

            # Link student to user
            await conn.execute(
                "UPDATE students SET user_id = $1 WHERE id = $2",
                user_id, student_id
            )

            # Assign student role
            await conn.execute(
                "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)",
                user_id, student_role_id
            )

        print("\n" + "="*100)
        print("STUDENT LOGIN ACCOUNT CREATED (PRODUCTION)")
        print("="*100)
        print(f"\nStudent: {student['first_name']} {student['last_name']}")
        print(f"Email:   {student_email}")
        print(f"Role:    Student")
        print(f"\n" + "="*100)
        print("LOGIN CREDENTIALS (save these)")
        print("="*100)
        print(f"Email:    {student_email}")
        print(f"Password: {password}")
        print("="*100)
        print(f"\n[WARNING] This password was printed to terminal only.")
        print(f"[WARNING] It is NOT stored in any file or git history.")
        print(f"[WARNING] Student can log in immediately and change password.\n")

        return 0

    except Exception as e:
        print(f"[ERROR] Failed to create account: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
