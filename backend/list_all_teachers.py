"""
List all teacher users (real + seed)
"""
import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
        ssl="require"
    )
    
    # Get ALL fairviewschoolng users (teachers + admins)
    users = await conn.fetch("""
        SELECT email, full_name, status, is_seed_account
        FROM users
        WHERE email LIKE '%fairviewschoolng.com'
        ORDER BY is_seed_account, email
    """)
    
    print("ALL FAIRVIEW USERS:")
    print()
    
    real = [u for u in users if not u['is_seed_account']]
    seed = [u for u in users if u['is_seed_account']]
    
    if real:
        print(f"REAL ACCOUNTS ({len(real)}):")
        for u in real:
            print(f"  {u['email']:35} {u['full_name']:30} {u['status']}")
    
    if seed:
        print(f"\nSEED ACCOUNTS ({len(seed)}):")
        for u in seed:
            print(f"  {u['email']:35} {u['full_name']:30}")
    
    await conn.close()

asyncio.run(main())
