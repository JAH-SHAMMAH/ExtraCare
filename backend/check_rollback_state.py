import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
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
