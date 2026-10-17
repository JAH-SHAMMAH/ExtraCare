import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
        ssl="require"
    )
    cols = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'user_roles'
        ORDER BY ordinal_position
    """)
    for c in cols:
        print(c["column_name"], "-", c["data_type"])
    await conn.close()

asyncio.run(main())
