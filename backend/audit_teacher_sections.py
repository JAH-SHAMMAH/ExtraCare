#!/usr/bin/env python3
"""
Audit: Do the 10 real teachers have TeacherSection assignments?
"""

import sys
import asyncio
import asyncpg

async def connect_db(db_url: str):
    clean_url = db_url.split('?')[0]
    conn = await asyncpg.connect(clean_url, ssl='require')
    return conn

async def main():
    if len(sys.argv) < 2:
        print("Usage: python audit_teacher_sections.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 140)
        print("AUDIT: TeacherSection Assignments")
        print("=" * 140)
        print()

        teacher_emails = [
            "biology@fairviewschoolng.com",
            "chemistry@fairviewschoolng.com",
            "crs@fairviewschoolng.com",
            "economics@fairviewschoolng.com",
            "english@fairviewschoolng.com",
            "geography@fairviewschoolng.com",
            "government@fairviewschoolng.com",
            "ict@fairviewschoolng.com",
            "mathematics@fairviewschoolng.com",
            "physics@fairviewschoolng.com",
        ]

        print("1. TEACHERSECTION ROWS FOR 10 REAL TEACHERS")
        print("-" * 140)
        print()

        for email in teacher_emails:
            teacher_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
            if not teacher_id:
                print(f"{email}: user not found")
                continue

            ts_rows = await conn.fetch(
                """
                SELECT ss.name as section_name
                FROM teacher_sections ts
                JOIN school_sections ss ON ts.section_id = ss.id
                WHERE ts.teacher_id = $1
                """,
                teacher_id
            )

            if ts_rows:
                print(f"{email}: {len(ts_rows)} section(s)")
                for ts in ts_rows:
                    print(f"    - {ts['section_name']}")
            else:
                print(f"{email}: ZERO TeacherSection assignments")

            print()

        print()
        print("2. WHAT SECTIONS EXIST IN DATABASE")
        print("-" * 140)
        print()

        sections = await conn.fetch("SELECT id, name FROM school_sections ORDER BY name")
        print(f"Sections ({len(sections)} total):")
        for s in sections:
            print(f"  - {s['name']} (id: {str(s['id'])[:8]}...)")

        print()
        print("3. ASSIGNED CLASSES -> THEIR SECTIONS")
        print("-" * 140)
        print()

        assigned_classes = await conn.fetch("""
            SELECT u.email, sc.name as class_name, ss.name as section_name
            FROM school_classes sc
            JOIN users u ON sc.teacher_id = u.id
            LEFT JOIN school_sections ss ON sc.section_id = ss.id
            WHERE u.email ILIKE '%@fairviewschoolng.com'
            AND u.job_title ILIKE '%teacher%'
            AND NOT sc.name LIKE '[SEED]%'
            ORDER BY u.email, sc.name
        """)

        print("Teacher -> Class -> Section:")
        for cls in assigned_classes:
            print(f"  {cls['email']}")
            print(f"    -> {cls['class_name']} (section: {cls['section_name'] or 'NULL'})")

        print()
        print("4. ASSIGNED SUBJECTS -> THEIR SECTIONS (via classes taking the subject)")
        print("-" * 140)
        print()

        assigned_subjects = await conn.fetch("""
            SELECT DISTINCT u.email, s.name as subject_name
            FROM subjects s
            JOIN users u ON s.teacher_id = u.id
            WHERE u.email ILIKE '%@fairviewschoolng.com'
            AND u.job_title ILIKE '%teacher%'
            ORDER BY u.email, s.name
        """)

        print("Teacher -> Subject:")
        for subj in assigned_subjects:
            sections_for_subject = await conn.fetch(
                """
                SELECT DISTINCT ss.name as section_name
                FROM timetables t
                JOIN school_classes sc ON t.class_id = sc.id
                LEFT JOIN school_sections ss ON sc.section_id = ss.id
                WHERE t.subject_id = (SELECT id FROM subjects WHERE name = $1)
                """,
                subj['subject_name']
            )

            print(f"  {subj['email']}")
            print(f"    -> {subj['subject_name']}", end="")
            if sections_for_subject:
                section_names = [s['section_name'] for s in sections_for_subject]
                print(f" (taught in: {', '.join(section_names)})")
            else:
                print(f" (no class assignments yet)")

        print()
        print("=" * 140)
        print("DIAGNOSIS")
        print("=" * 140)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
