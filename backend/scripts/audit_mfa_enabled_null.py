#!/usr/bin/env python3
import sys
import asyncio

async def main():
    if len(sys.argv) < 2:
        print("usage: python audit_mfa_enabled_null.py '<postgresql_url>'")
        return 2

    database_url = sys.argv[1].strip().split("?")[0]
    import asyncpg
    conn = await asyncpg.connect(database_url, ssl="require")

    try:
        rows = await conn.fetch(
            """
            SELECT id, email, full_name, status, created_at
            FROM users
            WHERE mfa_enabled IS NULL
            ORDER BY created_at DESC
            """
        )
        print(f"Found {len(rows)} users with NULL mfa_enabled:\n")
        for row in rows:
            print(f"{row['email']:<50} {row['full_name']:<30} {row['status']:<10}")
        print(f"\nTOTAL AFFECTED: {len(rows)}")
        return 0
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
