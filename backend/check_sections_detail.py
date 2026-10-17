import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
        ssl="require"
    )
    
    sections = await conn.fetch("""
        SELECT id, name, curriculum, position, level_aliases 
        FROM school_sections 
        ORDER BY position, name
    """)
    
    print("School sections detail:")
    for s in sections:
        print(f"\n  ID: {s['id']}")
        print(f"  Name: {s['name']}")
        print(f"  Curriculum: {s['curriculum']}")
        print(f"  Position: {s['position']}")
        print(f"  Level aliases: {s['level_aliases']}")
    
    await conn.close()

asyncio.run(main())
