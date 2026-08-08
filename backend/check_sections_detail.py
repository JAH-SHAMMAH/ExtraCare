import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
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
