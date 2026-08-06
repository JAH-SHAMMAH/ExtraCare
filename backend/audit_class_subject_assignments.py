#!/usr/bin/env python3
"""
Audit: What class/subject/timetable/section data exists in the DB?
Answers whether real assignment is possible or if data needs creation first.

Usage:
  python audit_class_subject_assignments.py <DATABASE_URL>

Example:
  python audit_class_subject_assignments.py "postgresql://user:pass@host:5432/school_db_onyz?ssl=require"
"""

import sys
import asyncio
import asyncpg
from collections import defaultdict

async def connect_db(db_url: str):
    """Connect to DB, stripping ?ssl=require from URL and passing ssl='require' separately."""
    clean_url = db_url.split('?')[0]
    conn = await asyncpg.connect(clean_url, ssl='require')
    return conn

async def main():
    if len(sys.argv) < 2:
        print("Usage: python audit_class_subject_assignments.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 120)
        print("AUDIT: Class / Subject / Timetable / Section Assignment Data")
        print("=" * 120)
        print()

        # 1. All SchoolClass entries
        print("1. SCHOOLCLASS TABLE (Classes, student counts, current teacher assignments)")
        print("-" * 120)
        print()

        classes = await conn.fetch("""
            SELECT
                c.id,
                c.name,
                c.level,
                c.academic_year,
                c.teacher_id,
                u.email as teacher_email,
                COUNT(DISTINCT s.id) as student_count
            FROM school_classes c
            LEFT JOIN users u ON c.teacher_id = u.id
            LEFT JOIN students s ON c.id = s.class_id
            GROUP BY c.id, c.name, c.level, c.academic_year, c.teacher_id, u.email
            ORDER BY c.level, c.name
        """)

        if classes:
            print(f"Found {len(classes)} classes:\n")
            for cls in classes:
                teacher_info = f"{cls['teacher_email']}" if cls['teacher_email'] else "UNASSIGNED"
                print(f"  {cls['name']} ({cls['level']}, {cls['academic_year']})")
                print(f"    Students: {cls['student_count']}")
                print(f"    Teacher: {teacher_info}")
                print()
        else:
            print("⚠️  No classes found in database\n")

        # 2. All Subject entries
        print("=" * 120)
        print("2. SUBJECT TABLE (Subjects, current teacher assignments)")
        print("-" * 120)
        print()

        subjects = await conn.fetch("""
            SELECT
                s.id,
                s.name,
                s.code,
                s.teacher_id,
                u.email as teacher_email,
                COUNT(DISTINCT g.id) as grade_count
            FROM subjects s
            LEFT JOIN users u ON s.teacher_id = u.id
            LEFT JOIN grades g ON s.id = g.subject_id
            GROUP BY s.id, s.name, s.code, s.teacher_id, u.email
            ORDER BY s.name
        """)

        if subjects:
            print(f"Found {len(subjects)} subjects:\n")
            
            # Check which subjects match the 10 real teacher emails
            real_teacher_subjects = {
                "biology": "biology@fairviewschoolng.com",
                "chemistry": "chemistry@fairviewschoolng.com",
                "crs": "crs@fairviewschoolng.com",
                "economics": "economics@fairviewschoolng.com",
                "english": "english@fairviewschoolng.com",
                "geography": "geography@fairviewschoolng.com",
                "government": "government@fairviewschoolng.com",
                "ict": "ict@fairviewschoolng.com",
                "mathematics": "mathematics@fairviewschoolng.com",
                "physics": "physics@fairviewschoolng.com",
            }
            
            for subj in subjects:
                subject_key = subj['name'].lower()
                expected_teacher = real_teacher_subjects.get(subject_key)
                teacher_info = f"{subj['teacher_email']}" if subj['teacher_email'] else "UNASSIGNED"
                
                match_status = ""
                if expected_teacher:
                    if subj['teacher_email'] == expected_teacher:
                        match_status = " ✓ (correctly assigned)"
                    else:
                        match_status = f" ✗ (should be {expected_teacher}, is {teacher_info})"
                
                print(f"  {subj['name']} ({subj['code']}){match_status}")
                print(f"    Current teacher: {teacher_info}")
                print(f"    Grade records: {subj['grade_count']}")
                print()
        else:
            print("⚠️  No subjects found in database\n")

        # 3. Timetable entries
        print("=" * 120)
        print("3. TIMETABLE TABLE (Class/subject/teacher time slots)")
        print("-" * 120)
        print()

        timetable_count = await conn.fetchval("SELECT COUNT(*) FROM timetable")
        if timetable_count and timetable_count > 0:
            print(f"Found {timetable_count} timetable entries\n")
            
            timetable_sample = await conn.fetch("""
                SELECT
                    t.id,
                    c.name as class_name,
                    s.name as subject_name,
                    u.email as teacher_email,
                    t.day_of_week,
                    t.start_time,
                    t.end_time,
                    t.room
                FROM timetable t
                LEFT JOIN school_classes c ON t.class_id = c.id
                LEFT JOIN subjects s ON t.subject_id = s.id
                LEFT JOIN users u ON t.teacher_id = u.id
                ORDER BY c.name, t.day_of_week, t.start_time
                LIMIT 20
            """)
            
            print("Sample (first 20):\n")
            for entry in timetable_sample:
                day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                day = day_names[entry['day_of_week']] if entry['day_of_week'] is not None and entry['day_of_week'] < len(day_names) else "Unknown"
                print(f"  {entry['class_name']} → {entry['subject_name']}")
                print(f"    {day} {entry['start_time']}-{entry['end_time']} (Room: {entry['room']})")
                print(f"    Teacher: {entry['teacher_email'] or 'UNASSIGNED'}")
                print()
        else:
            print("⚠️  No timetable entries found (empty/schema missing)\n")

        # 4. TeacherSection assignments
        print("=" * 120)
        print("4. TEACHERSECTION TABLE (Teacher → Section assignments)")
        print("-" * 120)
        print()

        teacher_sections = await conn.fetch("""
            SELECT
                u.email,
                u.full_name,
                s.name as section_name,
                COUNT(*) as count
            FROM teacher_sections ts
            JOIN users u ON ts.teacher_id = u.id
            JOIN school_sections s ON ts.section_id = s.id
            WHERE u.email ILIKE '%@fairviewschoolng.com'
            GROUP BY u.email, u.full_name, s.name
            ORDER BY u.email
        """)

        if teacher_sections:
            print(f"Found {len(teacher_sections)} teacher-section assignments:\n")
            for ts in teacher_sections:
                print(f"  {ts['email']} ({ts['full_name']}) → {ts['section_name']}")
        else:
            print("⚠️  No teacher-section assignments found (all 10 real teachers unassigned)\n")

        # 5. Summary and readiness assessment
        print("=" * 120)
        print("5. READINESS ASSESSMENT")
        print("=" * 120)
        print()

        class_count = len(classes) if classes else 0
        subject_count = len(subjects) if subjects else 0
        timetable_count = timetable_count or 0
        section_count = len(teacher_sections) if teacher_sections else 0

        print(f"Class records: {class_count}")
        print(f"Subject records: {subject_count}")
        print(f"Timetable entries: {timetable_count}")
        print(f"Teacher-section assignments: {section_count}")
        print()

        if class_count > 0 and subject_count > 0:
            print("✓ READY FOR REAL ASSIGNMENT")
            print("  Sufficient class/subject data exists in the database.")
            print("  Can proceed with assigning the 10 real teachers to existing classes/subjects.")
        elif class_count > 0:
            print("⚠️  PARTIAL DATA")
            print("  Classes exist but subjects are missing or incomplete.")
            print("  May need to create or seed subject records first.")
        else:
            print("✗ DATA MISSING")
            print("  Classes and/or subjects not yet in database.")
            print("  Need to create class/student/subject records before teacher assignment.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
