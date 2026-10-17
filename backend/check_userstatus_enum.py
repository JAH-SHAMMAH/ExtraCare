import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
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
