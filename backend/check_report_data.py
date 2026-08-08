import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    
    # Find tables with "report" in the name
    tables = await conn.fetch("""
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' AND tablename LIKE '%report%'
        ORDER BY tablename
    """)
    
    print("Tables with 'report' in name:")
    for t in tables:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {t['tablename']}")
        print(f"  {t['tablename']}: {count} rows")
    
    # Check class section assignments
    class_section_count = await conn.fetchval(
        "SELECT COUNT(*) FROM school_classes WHERE section_id IS NOT NULL"
    )
    print(f"\nClasses assigned to sections: {class_section_count}")
    
    await conn.close()

asyncio.run(main())
