import asyncio
import asyncpg
import bcrypt

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )

    # Set a known, fresh password
    test_password = "TestPassword123!"
    new_hash = bcrypt.hashpw(test_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

    await conn.execute(
        "UPDATE users SET hashed_password = $1 WHERE email = $2",
        new_hash, "abebi.abioye@fairviewschoolng.com"
    )

    # Now fetch it back EXACTLY as the app would via asyncpg
    row = await conn.fetchrow(
        "SELECT hashed_password FROM users WHERE email = $1",
        "abebi.abioye@fairviewschoolng.com"
    )
    fetched_hash = row["hashed_password"]

    print("Type of fetched hash:", type(fetched_hash))
    print("Fetched hash value:", fetched_hash)

    # Now try the EXACT verify_password logic from security.py
    try:
        result = bcrypt.checkpw(test_password.encode("utf-8"), fetched_hash.encode("utf-8"))
        print("bcrypt.checkpw result:", result)
    except Exception as e:
        print("ERROR during checkpw:", e)

    print()
    print("If result is True: the hash/verify logic works fine outside the app.")
    print("Use this password to test login on the real portal:")
    print("Email:   ", "abebi.abioye@fairviewschoolng.com")
    print("Password:", test_password)

    await conn.close()

asyncio.run(main())
