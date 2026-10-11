import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
        ssl="require"
    )
    result = await conn.execute(
        "UPDATE users SET email = $1 WHERE id = $2",
        "abebi.abioye@fairviewschoolng.com", "571083013ecaa477"
    )
    print("Update result:", result)

    # verify
    row = await conn.fetchrow("SELECT id, email FROM users WHERE id = $1", "571083013ecaa477")
    print("Confirmed user row:", dict(row))
    await conn.close()

asyncio.run(main())
