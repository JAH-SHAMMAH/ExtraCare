import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
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
