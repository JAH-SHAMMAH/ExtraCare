#!/usr/bin/env python3
"""
DRY-RUN: Show which user_roles rows will be changed for the 10 real teachers.
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
        print("Usage: python reassign_teacher_roles_dryrun.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 100)
        print("DRY-RUN: Reassign 10 teachers from staff to teacher role")
        print("=" * 100)
        print()

        staff_role = await conn.fetchrow("SELECT id FROM roles WHERE slug = 'staff'")
        teacher_role = await conn.fetchrow("SELECT id FROM roles WHERE slug = 'teacher'")

        if not staff_role or not teacher_role:
            print("Could not find staff or teacher role")
            await conn.close()
            return

        staff_role_id = staff_role['id']
        teacher_role_id = teacher_role['id']

        print(f"staff role ID:   {staff_role_id}")
        print(f"teacher role ID: {teacher_role_id}")
        print()
        print("=" * 100)
        print()

        count = 0
        for email in TEACHER_EMAILS:
            user = await conn.fetchrow(
                "SELECT id, email, full_name FROM users WHERE email = $1",
                email
            )

            if not user:
                print(f"{email} - NOT FOUND in users table")
                print()
                continue

            current_roles = await conn.fetch(
                """
                SELECT ur.user_id, ur.role_id, r.slug, r.name
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.id
                WHERE ur.user_id = $1
                ORDER BY r.slug
                """,
                user['id']
            )

            count += 1
            print(f"{count}. {email}")
            print(f"   User ID: {user['id']}")
            print(f"   Name: {user['full_name']}")
            print()

            if current_roles:
                print("   CURRENT user_roles entries:")
                for role in current_roles:
                    print(f"     - role_id: {role['role_id']}, slug: {role['slug']}")
                print()
            else:
                print("   CURRENT user_roles entries: NONE")
                print()

            print("   CHANGES:")
            print(f"     - DELETE user_roles where user_id={user['id']} AND role_id={staff_role_id}")
            print(f"     - INSERT user_roles (user_id={user['id']}, role_id={teacher_role_id})")
            print()

        print("=" * 100)
        print("WHAT WILL HAPPEN:")
        print("=" * 100)
        print(f"{count} teachers will be reassigned")
        print("Each teacher: DELETE staff role, INSERT teacher role")
        print("No other accounts or roles touched")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
