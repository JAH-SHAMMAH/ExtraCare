import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
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
