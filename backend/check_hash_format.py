import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    row = await conn.fetchrow(
        "SELECT id, email, hashed_password, status, LENGTH(hashed_password) as hash_len FROM users WHERE email = $1",
        "abebi.abioye@fairviewschoolng.com"
    )
    print("email:      ", row["email"])
    print("status:     ", repr(row["status"]))
    print("hash:       ", row["hashed_password"])
    print("hash length:", row["hash_len"])
    print("starts $2b$12$:", row["hashed_password"].startswith("$2b$12$") if row["hashed_password"] else None)
    await conn.close()

asyncio.run(main())
