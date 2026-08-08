import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    
    # Find user IDs
    users = await conn.fetch("""
        SELECT id, email FROM users 
        WHERE email IN ('seed-classteacher@fairviewschoolng.com', 'mathematics@fairviewschoolng.com')
    """)
    
    print("Users found:")
    for u in users:
        print(f"  {u['email']}: {u['id']}")
    
    # Check teacher_sections for each
    for u in users:
        sections = await conn.fetch("""
            SELECT ts.id, s.name FROM teacher_sections ts
            JOIN school_sections s ON ts.section_id = s.id
            WHERE ts.teacher_id = $1
        """, u['id'])
        
        if sections:
            print(f"\n{u['email']} has sections:")
            for s in sections:
                print(f"  - {s['name']}")
        else:
            print(f"\n{u['email']}: NO teacher_sections assigned")
    
    # Check what sections exist
    all_sections = await conn.fetch("SELECT id, name FROM school_sections ORDER BY name")
    print("\n\nAvailable school sections:")
    for s in all_sections:
        print(f"  {s['name']} (id: {s['id']})")
    
    await conn.close()

asyncio.run(main())
