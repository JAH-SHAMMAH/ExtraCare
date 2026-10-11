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
    # GENERATED, never committed. This script used to carry the literal
    # password it set, so the account it reset was readable by anyone with the
    # repository. It is printed once below and stored nowhere -- the same
    # convention scripts/create_student_login_prod.py already documents.
    new_password = secrets.token_urlsafe(12)
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode()
    result = await conn.execute(
        "UPDATE users SET hashed_password = $1 WHERE email = $2",
        hashed, "mathematics@fairviewschoolng.com"
    )
    print("Updated:", result)
    print("New password for mathematics@fairviewschoolng.com:", new_password)
    await conn.close()

asyncio.run(main())
