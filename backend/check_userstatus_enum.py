import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    rows = await conn.fetch("""
        SELECT enumlabel FROM pg_enum
        JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
        WHERE pg_type.typname = 'userstatus'
        ORDER BY enumsortorder
    """)
    print("Valid userstatus enum values:")
    for r in rows:
        print(" -", r["enumlabel"])
    await conn.close()

asyncio.run(main())
