import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    org = await conn.fetchrow("SELECT id, slug, name, is_active FROM organizations WHERE id = $1", "8550ce5f-d9f6-48ef-8382-eff036da556a")
    print("Org row:", dict(org) if org else "NOT FOUND")
    await conn.close()

asyncio.run(main())
