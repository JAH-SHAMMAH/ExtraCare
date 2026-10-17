import os
import asyncio
import asyncpg
import bcrypt

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
        ssl="require"
    )
    new_password = os.environ["NEW_PASSWORD"]
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode()
    result = await conn.execute(
        "UPDATE users SET hashed_password = $1 WHERE email = $2",
        hashed, "mathematics@fairviewschoolng.com"
    )
    print("Updated:", result)
    print("New password for mathematics@fairviewschoolng.com:", new_password)
    await conn.close()

asyncio.run(main())
