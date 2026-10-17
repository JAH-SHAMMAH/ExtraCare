import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
        ssl="require"
    )
    rows = await conn.fetch("""
        SELECT r.slug, r.name
        FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = (SELECT id FROM users WHERE email ILIKE '%seed%classteacher%')
    """)
    for r in rows:
        print(r["slug"], "-", r["name"])
    await conn.close()

asyncio.run(main())
