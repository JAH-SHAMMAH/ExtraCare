import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    tables = await conn.fetch("""
        SELECT table_name FROM information_schema.tables
        WHERE table_name ILIKE '%timetable%'
    """)
    print("Tables matching timetable:")
    for t in tables:
        print(" -", t["table_name"])

    if tables:
        cols = await conn.fetch(f"""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = '{tables[0]["table_name"]}'
            ORDER BY ordinal_position
        """)
        print()
        print(f"Columns in {tables[0]['table_name']}:")
        for c in cols:
            print(" -", c["column_name"], "-", c["data_type"])

    await conn.close()

asyncio.run(main())
