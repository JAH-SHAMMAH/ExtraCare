import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
        ssl="require"
    )
    rows = await conn.fetch("""
        SELECT ss.name, COUNT(sc.id) as class_count
        FROM school_sections ss
        LEFT JOIN school_classes sc ON sc.section_id = ss.id
        GROUP BY ss.name
        ORDER BY ss.name
    """)
    for r in rows:
        print(r["name"], "-", r["class_count"], "classes")
    await conn.close()

asyncio.run(main())
