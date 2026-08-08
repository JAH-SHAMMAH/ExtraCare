import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
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
