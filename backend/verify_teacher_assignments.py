"""
Verify: Are the 6 form teacher assignments still in school_classes.teacher_id?
"""
import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(
            "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
            ssl="require",
            timeout=10
        )
    except Exception as e:
        print(f"Connection error: {e}")
        print("Render database may be temporarily unavailable. Retrying...")
        return
    
    print("=" * 80)
    print("VERIFY: Class teacher assignments in school_classes.teacher_id")
    print("=" * 80)
    
    # Query school_classes with their assigned teachers
    classes = await conn.fetch("""
        SELECT sc.id, sc.name, sc.level, sc.teacher_id, u.email, u.full_name
        FROM school_classes sc
        LEFT JOIN users u ON sc.teacher_id = u.id
        WHERE sc.teacher_id IS NOT NULL
        ORDER BY sc.level, sc.name
    """)
    
    if not classes:
        print("\nWARNING: NO classes have teacher_id assigned!")
    else:
        print(f"\nFound {len(classes)} class teacher assignments:\n")
        for cls in classes:
            print(f"  {cls['name']:30} ({cls['level']:15}) -> {cls['email']}")
    
    # Also list what subjects are assigned to which teachers
    print("\n" + "=" * 80)
    print("Subject assignments (via subjects.teacher_id):")
    print("=" * 80)
    
    subjects = await conn.fetch("""
        SELECT s.name as subject_name, u.email, u.full_name
        FROM subjects s
        LEFT JOIN users u ON s.teacher_id = u.id
        WHERE s.teacher_id IS NOT NULL
        ORDER BY u.email, s.name
    """)
    
    if subjects:
        for subj in subjects:
            print(f"  {subj['subject_name']:40} -> {subj['email']}")
    else:
        print("  (no subjects assigned)")
    
    await conn.close()

asyncio.run(main())
