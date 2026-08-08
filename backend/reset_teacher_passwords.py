"""
Reset passwords for one or more teachers.
Parameterized for reuse.
"""
import asyncio
import asyncpg
import bcrypt

async def reset_password(email: str, password: str):
    """Reset password for a specific teacher email."""
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    result = await conn.execute(
        "UPDATE users SET hashed_password = $1 WHERE email = $2",
        hashed, email
    )

    await conn.close()
    return result

async def main():
    print("\n" + "="*100)
    print("TEACHER PASSWORD RESET")
    print("="*100 + "\n")

    # Define teachers and their new passwords
    teachers = [
        ("mathematics@fairviewschoolng.com", "Mathematics#2026"),
        ("geography@fairviewschoolng.com", "Geography#2026"),
    ]

    for email, password in teachers:
        await reset_password(email, password)
        print(f"{email}")
        print(f"  New password: {password}")
        print()

    print("="*100)
    print("PASSWORDS UPDATED")
    print("="*100 + "\n")

asyncio.run(main())
