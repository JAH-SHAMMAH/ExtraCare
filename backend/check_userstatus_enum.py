import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
        ssl="require"
    )
    rows = await conn.fetch("""
        SELECT enumlabel FROM pg_enum
        JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
        WHERE pg_type.typname = 'userstatus'
        ORDER BY enumsortorder
    """)
    print("Valid userstatus enum values:")
    for r in rows:
        print(" -", r["enumlabel"])
    await conn.close()

asyncio.run(main())
