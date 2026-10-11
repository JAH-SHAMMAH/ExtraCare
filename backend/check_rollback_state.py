import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
        ssl="require"
    )
    rows = await conn.fetch("""
        SELECT name, code FROM subjects 
        WHERE name IN ('Biology', 'Chemistry', 'Economics', 'Geography', 'Government', 'Physics')
        ORDER BY name
    """)
    if rows:
        print(f"FOUND {len(rows)} subjects still in DB:")
        for r in rows:
            print(" -", r["name"], r["code"])
    else:
        print("NONE FOUND - all 6 rolled back cleanly, as expected")

    await conn.close()

asyncio.run(main())
