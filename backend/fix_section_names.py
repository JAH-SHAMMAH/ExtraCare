import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    
    # Map old names to new names
    mapping = {
        "High": "Secondary",
        "Junior": "Primary", 
        "Senior": "Secondary"  # Wait, both High and Senior would be Secondary?
    }
    
    # First, check what we have
    sections = await conn.fetch("SELECT id, name FROM school_sections ORDER BY name")
    print("Current sections:")
    for s in sections:
        print(f"  {s['name']} (id: {s['id']})")
    
    await conn.close()

asyncio.run(main())
