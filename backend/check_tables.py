import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
        ssl="require"
    )
    
    tables = await conn.fetch("""
        SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename
    """)
    
    print("Available tables:")
    for t in tables:
        print(f"  {t['tablename']}")
    
    await conn.close()

asyncio.run(main())
