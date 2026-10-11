import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
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
