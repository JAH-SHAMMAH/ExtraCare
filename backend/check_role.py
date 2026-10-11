import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
        ssl="require"
    )
    row = await conn.fetchrow("SELECT slug, permissions FROM roles WHERE slug = 'teacher'")
    print(row)
    await conn.close()

asyncio.run(main())
