#!/usr/bin/env python3
import sys
import asyncio

async def main():
    if len(sys.argv) < 2:
        print("usage: python backfill_mfa_enabled_false.py '<postgresql_url>'")
        return 2

    database_url = sys.argv[1].strip().split("?")[0]
    import asyncpg
    conn = await asyncpg.connect(database_url, ssl="require")

    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE mfa_enabled IS NULL")
        if count == 0:
            print("[OK] No records to backfill")
            return 0

        print(f"Backfilling {count} records...")
        async with conn.transaction():
            await conn.execute("UPDATE users SET mfa_enabled = False WHERE mfa_enabled IS NULL")
        print(f"[OK] Updated {count} user records")
        return 0
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
