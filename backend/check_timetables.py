import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require",
        timeout=10
    )
    
    print("=" * 80)
    print("TIMETABLE-BASED SUBJECT ASSIGNMENTS")
    print("=" * 80)
    print()
    
    rows = await conn.fetch("""
        SELECT DISTINCT s.name as subject_name, u.email as teacher_email
        FROM timetables t
        JOIN subjects s ON t.subject_id = s.id
        JOIN users u ON t.teacher_id = u.id
        WHERE u.email ILIKE '%@fairviewschoolng.com'
        ORDER BY s.name
    """)
    
    if rows:
        print(f"Found {len(rows)} Timetable subject assignments:\n")
        for row in rows:
            print(f"  {row['subject_name']:40} -> {row['teacher_email']}")
    else:
        print("ERROR: No Timetable assignments found!")
    
    # Also show the class scoping
    print("\n" + "=" * 80)
    print("CLASS SCOPING FOR EACH TIMETABLE ASSIGNMENT:")
    print("=" * 80)
    print()
    
    classes = await conn.fetch("""
        SELECT DISTINCT s.name as subject_name, u.email, sc.name as class_name, sc.level
        FROM timetables t
        JOIN subjects s ON t.subject_id = s.id
        JOIN users u ON t.teacher_id = u.id
        JOIN school_classes sc ON t.class_id = sc.id
        WHERE u.email ILIKE '%@fairviewschoolng.com'
        ORDER BY u.email, s.name, sc.level, sc.name
    """)
    
    current_subject = None
    current_teacher = None
    for row in classes:
        key = (row['subject_name'], row['email'])
        if key != (current_subject, current_teacher):
            current_subject = row['subject_name']
            current_teacher = row['email']
            print(f"{current_teacher} - {current_subject}:")
        print(f"    {row['class_name']:30} ({row['level']})")
    
    await conn.close()

asyncio.run(main())
