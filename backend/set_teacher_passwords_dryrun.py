#!/usr/bin/env python3
"""
DRY-RUN: Show which real teachers will get passwords, without writing.
"""

import sys
import asyncio
import asyncpg

async def connect_db(db_url: str):
    clean_url = db_url.split('?')[0]
    conn = await asyncpg.connect(clean_url, ssl='require')
    return conn

async def main():
    if len(sys.argv) < 2:
        print("Usage: python set_teacher_passwords_dryrun.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        teachers = await conn.fetch("""
            SELECT
                id,
                email,
                full_name,
                job_title,
                hashed_password IS NOT NULL as has_password,
                created_at
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
        print("DRY-RUN: Real Teachers That Will Receive Passwords")
        print("=" * 80)
        print(f"\nTotal teachers to update: {len(teachers)}\n")

        for idx, teacher in enumerate(teachers, 1):
            status = "needs password" if not teacher["has_password"] else "already has password (will replace)"
            print(f"{idx}. {teacher['email']}")
            print(f"   Name: {teacher['full_name']}")
            print(f"   Role: {teacher['job_title']}")
            print(f"   Status: {status}")
            print()

        print("=" * 80)
        print("WHAT WILL HAPPEN:")
        print("=" * 80)
        print(f"Generate {len(teachers)} unique passwords (1 per teacher)")
        print("Hash each password using bcrypt")
        print("Update database: users.hashed_password for each teacher")
        print("Print email + password pairs to terminal only")
        print("No files written")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
