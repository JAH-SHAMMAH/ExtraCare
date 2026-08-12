import asyncio
import asyncpg
import secrets
import string
import bcrypt

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    password = "".join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*()") for _ in range(16))
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

    result = await conn.execute(
        "UPDATE users SET hashed_password = $1 WHERE id = $2",
        hashed, "571083013ecaa477"
    )
    print("Update result:", result)
    print("New password:", password)
    await conn.close()

asyncio.run(main())
