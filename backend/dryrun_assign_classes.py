"""
DRY RUN: Assign existing school_classes to new school_sections.
Maps based on class level (Early Years → Nursery, Primary → Primary, Secondary → Secondary).
Does NOT write to database.
"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    
    # Get the new section IDs we're about to create
    # (In real execution, these would be returned from step 1)
    # For now, using the UUIDs from dryrun_create_sections.py
    sections_map = {
        "Nursery": "d5b21129-7d0a-4935-9f59-c424d99786a8",
        "Primary": "31a41cb4-0631-4c19-9c7d-4ca7cf1dd2c1",
        "Secondary": "068a9b5a-8588-4b86-96c4-0d587e734622",
    }
    
    # Define class-to-section mapping based on level
    class_mappings = {
        "Early Years": "Nursery",
        "Primary": "Primary",
        "Secondary": "Secondary",
    }
    
    # Fetch all existing classes
    classes = await conn.fetch("""
        SELECT id, name, level FROM school_classes
        WHERE section_id IS NULL
        ORDER BY level, name
    """)
    
    print("=" * 80)
    print("DRY RUN: ASSIGN SCHOOL_CLASSES TO NEW SECTIONS")
    print("=" * 80)
    
    assignments_by_section = {}
    
    for cls in classes:
        target_section = class_mappings.get(cls['level'])
        if target_section:
            if target_section not in assignments_by_section:
                assignments_by_section[target_section] = []
            assignments_by_section[target_section].append(cls)
    
    total_updates = 0
    
    for section_name in ["Nursery", "Primary", "Secondary"]:
        section_id = sections_map[section_name]
        classes_for_section = assignments_by_section.get(section_name, [])
        
        print(f"\n{section_name} section (id: {section_id})")
        print(f"  Classes to assign: {len(classes_for_section)}")
        
        for cls in classes_for_section:
            print(f"    • {cls['name']:30} (level: {cls['level']})")
            total_updates += 1
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print(f"  • Will UPDATE {total_updates} rows in school_classes")
    print(f"  • Mapping: Early Years → Nursery, Primary → Primary, Secondary → Secondary")
    print("=" * 80)
    
    await conn.close()

asyncio.run(main())
