#!/usr/bin/env python3
"""
Audit real teacher accounts: what role/role_id are they ACTUALLY assigned?
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
        print("Usage: python audit_teacher_roles.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 100)
        print("SCHEMA EXPLORATION: How is role assignment stored?")
        print("=" * 100)
        print()

        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'users'
            AND column_name LIKE '%role%'
            ORDER BY column_name
        """)

        if columns:
            print("Found role-related columns on users table:")
            for col in columns:
                print(f"  - {col['column_name']}: {col['data_type']}")
        else:
            print("No role_* columns found on users table")
        print()

        roles_table = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='roles')"
        )
        if roles_table:
            print("Found roles table")
            roles = await conn.fetch("SELECT id, name, slug FROM roles LIMIT 20")
            print(f"  Available roles ({len(roles)} total):")
            for role in roles:
                print(f"    - {role['slug']} (id: {role['id']}, name: {role['name']})")
        else:
            print("No roles table found")
        print()

        user_roles_table = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='user_roles')"
        )
        if user_roles_table:
            print("Found user_roles junction table")
        else:
            print("No user_roles junction table found")
        print()

        print("=" * 100)
        print("REAL TEACHER ACCOUNTS: Role assignments (vs seed-classteacher)")
        print("=" * 100)
        print()

        seed_teacher = await conn.fetchrow(
            "SELECT * FROM users WHERE email ILIKE '%seed%classteacher%' LIMIT 1"
        )

        if seed_teacher:
            print("REFERENCE: seed-classteacher account")
            print(f"  Email: {seed_teacher['email']}")
            if 'role_id' in seed_teacher.keys():
                print(f"  role_id: {seed_teacher['role_id']}")
            if 'role' in seed_teacher.keys():
                print(f"  role: {seed_teacher['role']}")
            print()

            if user_roles_table:
                seed_roles = await conn.fetch(
                    """
                    SELECT r.id, r.slug, r.name
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = $1
                    """,
                    seed_teacher['id']
                )
                if seed_roles:
                    print("  Roles (via user_roles junction):")
                    for role in seed_roles:
                        print(f"    - {role['slug']} (id: {role['id']}, name: {role['name']})")
                else:
                    print("  No roles assigned (via user_roles junction)")
                print()
        else:
            print("seed-classteacher account not found")
            print()

        real_teachers = await conn.fetch("""
            SELECT id, email, full_name, job_title
            FROM users
            WHERE email ILIKE '%@fairviewschoolng.com'
            AND job_title ILIKE '%teacher%'
            ORDER BY email
        """)

        print(f"REAL TEACHER ACCOUNTS ({len(real_teachers)} total):")
        print()

        for teacher in real_teachers:
            print(f"Email: {teacher['email']}")
            print(f"Name:  {teacher['full_name']}")

            teacher_full = await conn.fetchrow("SELECT * FROM users WHERE id = $1", teacher['id'])
            if 'role_id' in teacher_full.keys():
                print(f"role_id column: {teacher_full['role_id']}")
            if 'role' in teacher_full.keys():
                print(f"role column: {teacher_full['role']}")

            if user_roles_table:
                teacher_roles = await conn.fetch(
                    """
                    SELECT r.id, r.slug, r.name
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = $1
                    """,
                    teacher['id']
                )
                if teacher_roles:
                    print("Roles assigned:")
                    for role in teacher_roles:
                        print(f"  - {role['slug']} (id: {role['id']}, name: {role['name']})")
                else:
                    print("Roles assigned: NONE")
            print()

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
