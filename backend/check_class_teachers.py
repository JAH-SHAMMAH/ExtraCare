import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
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
