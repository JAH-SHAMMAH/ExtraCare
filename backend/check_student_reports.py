import asyncio
import asyncpg
from _dsn import dsn

async def main():
    conn = await asyncpg.connect(
        dsn(),
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
