#!/usr/bin/env python3
"""
Audit: What permissions does the "staff" role have vs "teacher"?
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
        print("Usage: python audit_staff_role_permissions.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 100)
        print("STAFF ROLE PERMISSIONS")
        print("=" * 100)
        print()

        staff_role = await conn.fetchrow(
            "SELECT id, name, slug FROM roles WHERE slug = 'staff'"
        )

        if not staff_role:
            print("staff role not found")
            await conn.close()
            return

        print(f"Role: {staff_role['name']} (slug: {staff_role['slug']}, id: {staff_role['id']})")
        print()

        staff_perms = await conn.fetch(
            """
            SELECT p.id, p.name, p.scope
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            WHERE rp.role_id = $1
            ORDER BY p.scope
            """,
            staff_role['id']
        )

        if staff_perms:
            print(f"Permissions granted to staff ({len(staff_perms)} total):")
            for perm in staff_perms:
                print(f"  - {perm['scope']} (name: {perm['name']})")
        else:
            print("No permissions granted to staff role")

        print()
        print("=" * 100)
        print("TEACHER ROLE PERMISSIONS")
        print("=" * 100)
        print()

        teacher_role = await conn.fetchrow(
            "SELECT id, name, slug FROM roles WHERE slug = 'teacher'"
        )

        if not teacher_role:
            print("teacher role not found")
            await conn.close()
            return

        print(f"Role: {teacher_role['name']} (slug: {teacher_role['slug']}, id: {teacher_role['id']})")
        print()

        teacher_perms = await conn.fetch(
            """
            SELECT p.id, p.name, p.scope
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            WHERE rp.role_id = $1
            ORDER BY p.scope
            """,
            teacher_role['id']
        )

        if teacher_perms:
            print(f"Permissions granted to teacher ({len(teacher_perms)} total):")
            for perm in teacher_perms:
                print(f"  - {perm['scope']} (name: {perm['name']})")
        else:
            print("No permissions granted to teacher role")

        print()
        print("=" * 100)
        print("COMPARISON")
        print("=" * 100)
        print()

        staff_scopes = set(p['scope'] for p in staff_perms)
        teacher_scopes = set(p['scope'] for p in teacher_perms)

        only_staff = staff_scopes - teacher_scopes
        only_teacher = teacher_scopes - staff_scopes
        common = staff_scopes & teacher_scopes

        if only_staff:
            print(f"Only in staff ({len(only_staff)}):")
            for scope in sorted(only_staff):
                print(f"  - {scope}")
            print()

        if only_teacher:
            print(f"Only in teacher ({len(only_teacher)}):")
            for scope in sorted(only_teacher):
                print(f"  - {scope}")
            print()

        if common:
            print(f"In both roles ({len(common)}):")
            for scope in sorted(common):
                print(f"  - {scope}")
            print()

        print("=" * 100)
        print("VERDICT")
        print("=" * 100)
        print()
        if only_staff and len(only_staff) > len(only_teacher):
            print("staff role is BROADER than teacher (has more permissions)")
            print("Assigning teachers to staff was the bug")
        elif not only_staff:
            print("teacher is a superset or equal to staff")
        else:
            print("staff is NOT broader - check why teachers see admin features")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
