#!/usr/bin/env python3
"""
SET REAL PASSWORDS: Generate unique passwords for all real teachers.
Prints credentials to terminal only — NEVER writes to file or git.
"""

import sys
import asyncio
import asyncpg
import secrets
import string
import bcrypt
from datetime import datetime

async def connect_db(db_url: str):
    clean_url = db_url.split('?')[0]
    conn = await asyncpg.connect(clean_url, ssl='require')
    return conn

def generate_password(length: int = 14) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(chars) for _ in range(length))

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python set_teacher_passwords_real.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        teachers = await conn.fetch("""
            SELECT id, email, full_name, job_title
            FROM users
            WHERE (
                job_title ILIKE '%teacher%'
                OR job_title ILIKE '%head%'
                OR job_title ILIKE '%coordinator%'
                OR job_title ILIKE '%officer%'
            )
            AND email ILIKE '%@fairviewschoolng.com'
            AND email NOT ILIKE '%seed%'
            AND email NOT LIKE 'seed-%'
            ORDER BY email
        """)

        if not teachers:
            print("No real teachers found in database.")
            await conn.close()
            return

        print("=" * 80)
        print("SETTING REAL PASSWORDS FOR TEACHERS")
        print("=" * 80)
        print(f"Updating {len(teachers)} teachers...\n")

        credentials = []
        for teacher in teachers:
            password = generate_password()
            hashed = hash_password(password)

            await conn.execute(
                "UPDATE users SET hashed_password = $1, updated_at = $2 WHERE id = $3",
                hashed, datetime.utcnow(), teacher["id"]
            )

            credentials.append({
                "email": teacher["email"],
                "name": teacher["full_name"],
                "password": password
            })

        print("=" * 80)
        print("PASSWORDS SET — TEACHER CREDENTIALS")
        print("=" * 80)

        for cred in credentials:
            print(f"Email:    {cred['email']}")
            print(f"Name:     {cred['name']}")
            print(f"Password: {cred['password']}")
            print()

        print(f"{len(credentials)} teachers updated successfully")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
