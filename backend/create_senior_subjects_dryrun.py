#!/usr/bin/env python3
"""
DRY-RUN: Create 6 Senior Secondary subjects + 18 Timetable rows.
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
        print("Usage: python create_senior_subjects_dryrun.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 140)
        print("DRY-RUN: Create 6 Senior Subjects + 18 Timetable Scoping Rows")
        print("=" * 140)
        print()

        new_subjects = [
            ("Biology", "BIO"),
            ("Chemistry", "CHE"),
            ("Economics", "ECO"),
            ("Geography", "GEO"),
            ("Government", "GOV"),
            ("Physics", "PHY"),
        ]

        subject_teachers = {
            "Biology": "biology@fairviewschoolng.com",
            "Chemistry": "chemistry@fairviewschoolng.com",
            "Economics": "economics@fairviewschoolng.com",
            "Geography": "geography@fairviewschoolng.com",
            "Government": "government@fairviewschoolng.com",
            "Physics": "physics@fairviewschoolng.com",
        }

        org_id = await conn.fetchval("SELECT org_id FROM school_classes LIMIT 1")

        teacher_ids = {}
        for email in set(subject_teachers.values()):
            teacher_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
            if teacher_id:
                teacher_ids[email] = teacher_id

        year_classes = await conn.fetch("""
            SELECT id, name FROM school_classes
            WHERE org_id = $1 AND (name = 'Year 10' OR name = 'Year 11' OR name = 'Year 12')
            ORDER BY name
        """, org_id)

        class_id_map = {c["name"]: c["id"] for c in year_classes}

        print("=" * 140)
        print("1. NEW SUBJECT ROWS (6 total)")
        print("=" * 140)
        print()

        for subject_name, code in new_subjects:
            existing = await conn.fetchval(
                "SELECT id FROM subjects WHERE name = $1 AND org_id = $2",
                subject_name, org_id
            )
            status = "INSERT"
            if existing:
                status = "ALREADY EXISTS (will skip)"

            print(f"{subject_name} ({code})")
            print(f"  Before: doesn't exist")
            print(f"  After:  name='{subject_name}', code='{code}', teacher_id=NULL, is_active=True")
            print(f"  Action: {status}")
            print()

        print()
        print("=" * 140)
        print("2. NEW TIMETABLE ROWS (18 total: 6 subjects x 3 years)")
        print("=" * 140)
        print()

        row_count = 0
        for subject_name, code in new_subjects:
            teacher_email = subject_teachers[subject_name]
            teacher_id = teacher_ids.get(teacher_email)

            for year in ["Year 10", "Year 11", "Year 12"]:
                class_id = class_id_map.get(year)
                if not class_id or not teacher_id:
                    print(f"{subject_name} + {year}: missing class or teacher, will skip")
                    continue

                row_count += 1
                print(f"{subject_name:15} -> {year} ({teacher_email})")
                print(f"  Before: doesn't exist")
                print(f"  After:  class_id={str(class_id)[:8]}..., subject_id=<new>, teacher_id={str(teacher_id)[:8]}..., day_of_week=-1")
                print(f"  Action: INSERT")
                print()

        print()
        print("=" * 140)
        print("SUMMARY")
        print("=" * 140)
        print()
        print(f"New subjects to create: 6")
        print(f"New Timetable rows to create: {row_count}")
        print(f"Total inserts: {6 + row_count}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
