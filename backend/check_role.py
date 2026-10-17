import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
        ssl="require"
    )
    row = await conn.fetchrow("SELECT slug, permissions FROM roles WHERE slug = 'teacher'")
    print(row)
    await conn.close()

asyncio.run(main())
