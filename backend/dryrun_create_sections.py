"""DRY RUN - STEP 1: Create new school_sections"""
import asyncio, asyncpg, uuid
from datetime import datetime

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require", timeout=10
    )
    
    org = await conn.fetchrow("SELECT id FROM organizations LIMIT 1")
    org_id = org['id']
    
    sections = [
        {"id": "d5b21129-7d0a-4935-9f59-c424d99786a8", "name": "Nursery", "curriculum": "eyfs", "position": 0},
        {"id": "31a41cb4-0631-4c19-9c7d-4ca7cf1dd2c1", "name": "Primary", "curriculum": "nigerian", "position": 1},
        {"id": "068a9b5a-8588-4b86-96c4-0d587e734622", "name": "Secondary", "curriculum": "nigerian", "position": 2},
    ]
    
    print("STEP 1: Create 3 new school_sections (already shown)\n")
    print("Section IDs for subsequent steps:")
    for s in sections:
        print(f"  {s['name']:12} : {s['id']}")
    
    await conn.close()

asyncio.run(main())
