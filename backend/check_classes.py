import os
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
        ssl="require"
    )
    
    # Get all classes grouped by section
    classes = await conn.fetch("""
        SELECT DISTINCT c.section_id, s.name as section_name, c.name, c.level
        FROM school_classes c
        LEFT JOIN school_sections s ON c.section_id = s.id
        ORDER BY s.name, c.level, c.name
    """)
    
    print("Classes by section:\n")
    current_section = None
    for cls in classes:
        if cls['section_name'] != current_section:
            current_section = cls['section_name']
            print(f"{current_section}:")
        print(f"  {cls['name']} (level: {cls['level']})")
    
    await conn.close()

asyncio.run(main())
