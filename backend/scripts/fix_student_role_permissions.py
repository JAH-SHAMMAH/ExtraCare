#!/usr/bin/env python3
"""
Fix student role permissions: remove write scopes, add timetable:read.

CHANGES:
- Remove: school:cbt:write
- Remove: school:classroom:write
- Add: school:timetable:read

Usage:
  python scripts/fix_student_role_permissions.py "postgresql://..."
"""

import sys
import asyncio
import json

async def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/fix_student_role_permissions.py '<postgresql_url>'")
        return 2

    database_url = sys.argv[1].strip().split("?")[0]
    import asyncpg
    conn = await asyncpg.connect(database_url, ssl="require")

    try:
        # Get current student role permissions
        role = await conn.fetchrow(
            "SELECT id, permissions FROM roles WHERE slug = 'student' LIMIT 1"
        )

        if not role:
            print("[ERROR] Student role not found")
            return 1

        current_perms = json.loads(role['permissions']) if isinstance(role['permissions'], str) else role['permissions'] or []

        print("\n" + "="*100)
        print("STUDENT ROLE PERMISSION FIX")
        print("="*100 + "\n")

        print("BEFORE:")
        print(f"  Current permissions ({len(current_perms)}):")
        for p in sorted(current_perms):
            print(f"    - {p}")

        # Apply changes
        new_perms = [p for p in current_perms if p not in [
            "school:cbt:write",
            "school:classroom:write"
        ]]

        # Add timetable:read if not already present
        if "school:timetable:read" not in new_perms:
            new_perms.append("school:timetable:read")

        new_perms.sort()

        print(f"\nAFTER:")
        print(f"  New permissions ({len(new_perms)}):")
        for p in sorted(new_perms):
            print(f"    - {p}")

        # Show changes
        removed = set(current_perms) - set(new_perms)
        added = set(new_perms) - set(current_perms)

        if removed:
            print(f"\nREMOVED ({len(removed)}):")
            for p in sorted(removed):
                print(f"  - {p}")

        if added:
            print(f"\nADDED ({len(added)}):")
            for p in sorted(added):
                print(f"  - {p}")

        # Update
        print(f"\nUpdating role {role['id']}...")
        await conn.execute(
            "UPDATE roles SET permissions = $1 WHERE id = $2",
            json.dumps(new_perms),
            role['id']
        )

        print("[OK] Role permissions updated successfully")
        print("="*100 + "\n")

        return 0

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
