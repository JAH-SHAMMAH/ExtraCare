import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
        ssl="require"
    )
    row = await conn.fetchrow("""
        SELECT s.id as student_id, s.email as student_email, s.user_id,
               u.id as user_id_actual, u.email as user_email
        FROM students s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.first_name = 'Abebi' AND s.last_name = 'Abioye'
    """)
    print(dict(row) if row else "NOT FOUND")
    await conn.close()

asyncio.run(main())
