import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
        ssl="require"
    )
    org = await conn.fetchrow("SELECT id, slug, name, is_active FROM organizations WHERE id = $1", "8550ce5f-d9f6-48ef-8382-eff036da556a")
    print("Org row:", dict(org) if org else "NOT FOUND")
    await conn.close()

asyncio.run(main())
