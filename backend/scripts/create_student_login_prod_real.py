#!/usr/bin/env python3
import sys
import asyncio
import secrets
import string
from datetime import datetime
import bcrypt
import asyncpg

async def main():
    if len(sys.argv) < 3:
        print("usage: create_student_login_prod_real.py <email> <postgresql_url>")
        return 2

    student_email = sys.argv[1].strip().lower()
    database_url = sys.argv[2].strip().split("?")[0]

    conn = await asyncpg.connect(database_url, ssl="require")

    try:
        student = await conn.fetchrow(
            "SELECT id, first_name, last_name, email FROM students WHERE LOWER(email) = LOWER($1)",
            student_email
        )
        if not student:
            print(f"[ERROR] Student not found: {student_email}")
            return 1

        student_id = student["id"]

        existing_user = await conn.fetchval(
            "SELECT id FROM users WHERE id = (SELECT user_id FROM students WHERE id = $1)",
            student_id
        )
        if existing_user:
            print(f"[ERROR] Student already has a user account linked")
            return 1

        org_id = await conn.fetchval("SELECT org_id FROM students WHERE id = $1", student_id)
        student_role_id = await conn.fetchval(
            "SELECT id FROM roles WHERE org_id = $1 AND slug = 'student'", org_id
        )
        if not student_role_id:
            print("[ERROR] Student role not found")
            return 1

        password = "".join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*()") for _ in range(16))
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

        now = datetime.utcnow()
        user_id = secrets.token_hex(8)

        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO users (id, org_id, email, full_name, hashed_password,
                    status, email_verified, is_deleted, created_at, updated_at, force_password_change)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                user_id, org_id, student["email"],
                f"{student['first_name']} {student['last_name']}",
                hashed, "ACTIVE", True, False, now, now, True
            )
            await conn.execute("UPDATE students SET user_id = $1 WHERE id = $2", user_id, student_id)
            await conn.execute(
                "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)", user_id, student_role_id
            )

        print("STUDENT LOGIN ACCOUNT CREATED (PRODUCTION)")
        print(f"Email:    {student['email']}")
        print(f"Password: {password}")
        return 0

    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
