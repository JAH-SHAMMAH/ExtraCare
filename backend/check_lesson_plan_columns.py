import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    cols = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'lesson_plans'
        AND column_name IN ('theme','sub_topic','the_hook','contact','sex_demographics',
                             'average_age','no_in_class','prerequisite_knowledge','rationale',
                             'methodologies','reference','success_criteria')
    """)
    print(f"{len(cols)}/12 new columns found:")
    for c in cols:
        print(" -", c["column_name"])
    await conn.close()

asyncio.run(main())
