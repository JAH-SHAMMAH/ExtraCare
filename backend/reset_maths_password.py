import asyncio
import asyncpg
import bcrypt

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    new_password = "Mathematics#2026"
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode()
    result = await conn.execute(
        "UPDATE users SET hashed_password = $1 WHERE email = $2",
        hashed, "mathematics@fairviewschoolng.com"
    )
    print("Updated:", result)
    print("New password for mathematics@fairviewschoolng.com:", new_password)
    await conn.close()

asyncio.run(main())
