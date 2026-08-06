#!/usr/bin/env python3
"""
REAL: Reassign 10 teachers from staff to teacher role.
"""

import sys
import asyncio
import asyncpg

async def connect_db(db_url: str):
    clean_url = db_url.split('?')[0]
    conn = await asyncpg.connect(clean_url, ssl='require')
    return conn

TEACHER_EMAILS = [
    "biology@fairviewschoolng.com",
    "chemistry@fairviewschoolng.com",
    "crs@fairviewschoolng.com",
    "economics@fairviewschoolng.com",
    "english@fairviewschoolng.com",
    "geography@fairviewschoolng.com",
    "government@fairviewschoolng.com",
    "ict@fairviewschoolng.com",
    "mathematics@fairviewschoolng.com",
    "physics@fairviewschoolng.com",
]

async def main():
    if len(sys.argv) < 2:
        print("Usage: python reassign_teacher_roles_real.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        staff_role = await conn.fetchrow("SELECT id FROM roles WHERE slug = 'staff'")
        teacher_role = await conn.fetchrow("SELECT id FROM roles WHERE slug = 'teacher'")
        staff_role_id = staff_role['id']
        teacher_role_id = teacher_role['id']

        print("=" * 100)
        print("REASSIGNING 10 TEACHERS: staff -> teacher")
        print("=" * 100)
        print()

        success = 0
        for email in TEACHER_EMAILS:
            user = await conn.fetchrow("SELECT id, full_name FROM users WHERE email = $1", email)
            if not user:
                print(f"{email} - NOT FOUND, skipped")
                continue

            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM user_roles WHERE user_id = $1 AND role_id = $2",
                    user['id'], staff_role_id
                )
                await conn.execute(
                    "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    user['id'], teacher_role_id
                )

            print(f"{email} ({user['full_name']}) - reassigned to teacher")
            success += 1

        print()
        print("=" * 100)
        print(f"{success} of {len(TEACHER_EMAILS)} teachers reassigned successfully")
        print("=" * 100)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
