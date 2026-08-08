import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    
    # Count records in major report-related tables
    count_reports = await conn.fetchval("SELECT COUNT(*) FROM student_reports")
    count_report_entries = await conn.fetchval("SELECT COUNT(*) FROM report_entries")
    count_assessments = await conn.fetchval("SELECT COUNT(*) FROM assessments")
    
    print("Report-related data:")
    print(f"  student_reports: {count_reports}")
    print(f"  report_entries: {count_report_entries}")
    print(f"  assessments: {count_assessments}")
    
    # Check if any class is actually assigned to a section
    class_section_count = await conn.fetchval(
        "SELECT COUNT(*) FROM school_classes WHERE section_id IS NOT NULL"
    )
    print(f"\n  school_classes with section_id assigned: {class_section_count}")
    
    await conn.close()

asyncio.run(main())
