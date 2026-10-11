import asyncio
import secrets
import asyncpg
import bcrypt
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
        ssl="require"
    )

    # Set a known, fresh password
    # GENERATED, never committed. This script used to carry the literal
    # password it set, so the account it reset was readable by anyone with the
    # repository. It is printed once below and stored nowhere -- the same
    # convention scripts/create_student_login_prod.py already documents.
    test_password = secrets.token_urlsafe(12)
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
