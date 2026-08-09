import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    rows = await conn.fetch("""
        SELECT split_part(email, '@', 2) as domain, COUNT(*) as count
        FROM students
        WHERE email IS NOT NULL
        GROUP BY domain
        ORDER BY count DESC
    """)
    print("Distinct email domains across ALL students:")
    for r in rows:
        print(f"  {r['domain']}: {r['count']} students")

    total = await conn.fetchval("SELECT COUNT(*) FROM students")
    with_email = await conn.fetchval("SELECT COUNT(*) FROM students WHERE email IS NOT NULL")
    print(f"\nTotal students: {total}")
    print(f"Students with email: {with_email}")

    await conn.close()

asyncio.run(main())
