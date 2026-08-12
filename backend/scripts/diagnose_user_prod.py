#!/usr/bin/env python3
import sys
import asyncio

async def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/diagnose_user_prod.py '<postgresql_url>'")
        return 2

    database_url = sys.argv[1].strip().split("?")[0]

    import asyncpg

    conn = await asyncpg.connect(database_url, ssl="require")

    try:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1",
            "abebi.abioye@fairviewschoolng.com"
        )

        if not user:
            print("[ERROR] User not found")
            return 1

        print("\n" + "="*100)
        print("FULL USER RECORD DUMP")
        print("="*100 + "\n")

        for key in user.keys():
            value = user[key]
            if isinstance(value, str) and len(value) > 80:
                display = f"{value[:77]}..."
            else:
                display = value
            print(f"{key:<30} = {display}")

        print("\n" + "="*100)
        print("LOGIN AUTHENTICATION CHECK")
        print("="*100 + "\n")

        org = await conn.fetchrow(
            "SELECT id, slug, is_active FROM organizations WHERE slug = $1",
            "fairview-school"
        )

        if not org:
            print("[ERROR] School org not found")
            return 1

        print(f"School org ID: {org['id']}")
        print(f"User org_id:   {user['org_id']}")
        print(f"Match:         {user['org_id'] == org['id']}")

        print(f"\nUser is_deleted:   {user['is_deleted']}")
        print(f"Must be False:     {user['is_deleted'] == False}")

        print(f"\nUser status:       {user['status']}")

        print(f"\nUser hashed_password exists: {user['hashed_password'] is not None}")

        roles = await conn.fetch(
            "SELECT r.id, r.slug, r.name FROM user_roles ur JOIN roles r ON ur.role_id = r.id WHERE ur.user_id = $1",
            user['id']
        )

        print(f"\nRoles assigned: {len(roles)}")
        for role in roles:
            print(f"  - {role['slug']} ({role['name']})")

        return 0

    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
