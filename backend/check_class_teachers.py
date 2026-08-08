import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    
    count = await conn.fetchval("SELECT COUNT(*) FROM class_pc_teachers")
    print(f"Total class_pc_teachers rows: {count}")
    
    if count > 0:
        rows = await conn.fetch("SELECT * FROM class_pc_teachers LIMIT 5")
        for row in rows:
            print(row)
    
    await conn.close()

asyncio.run(main())
