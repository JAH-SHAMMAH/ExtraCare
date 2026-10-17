import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
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
