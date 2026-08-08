"""
Audit: Which classes and subjects does each real teacher teach?
"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    
    # Get all real (non-seed) teacher users
    teachers = await conn.fetch("""
        SELECT id, email, full_name
        FROM users
        WHERE email LIKE '%fairviewschoolng.com'
        AND email NOT LIKE 'seed-%'
        ORDER BY email
    """)
    
    print("=" * 80)
    print("TEACHER ASSIGNMENTS AUDIT")
    print("=" * 80)
    
    for teacher in teachers:
        email = teacher['email']
        name = teacher['full_name'] or email.split('@')[0]
        teacher_id = teacher['id']
        
        # Find class teacher assignments
        classes = await conn.fetch("""
            SELECT DISTINCT sc.name, sc.level
            FROM class_pc_teachers cpt
            JOIN school_classes sc ON cpt.class_id = sc.id
            WHERE cpt.teacher_id = $1
            ORDER BY sc.level, sc.name
        """, teacher_id)
        
        # Find subject assignments
        subjects = await conn.fetch("""
            SELECT DISTINCT s.name
            FROM subjects s
            WHERE s.teacher_id = $1
            ORDER BY s.name
        """, teacher_id)
        
        if classes or subjects:
            print(f"\n{email} ({name})")
            if classes:
                print(f"  Form Teacher:")
                for cls in classes:
                    print(f"    {cls['name']:30} ({cls['level']})")
            if subjects:
                print(f"  Subject(s):")
                for subj in subjects:
                    print(f"    {subj['name']}")
    
    await conn.close()

asyncio.run(main())
