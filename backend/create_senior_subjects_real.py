#!/usr/bin/env python3
"""
REAL WRITE: Create 6 Senior Secondary subjects + 18 Timetable rows.
Uses start_time="00:00", end_time="00:01" as sentinel placeholders.
"""

import sys
import asyncio
import asyncpg
from uuid import uuid4
from datetime import datetime

async def connect_db(db_url: str):
    clean_url = db_url.split('?')[0]
    conn = await asyncpg.connect(clean_url, ssl='require')
    return conn

async def main():
    if len(sys.argv) < 2:
        print("Usage: python create_senior_subjects_real.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 140)
        print("REAL WRITE: Create 6 Senior Subjects + 18 Timetable Rows")
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
        print("INSERTING: 6 subjects + 18 Timetable rows (atomic per subject)")
        print("=" * 140)
        print()

        subject_count = 0
        timetable_count = 0

        for subject_name, code in new_subjects:
            existing = await conn.fetchval(
                "SELECT id FROM subjects WHERE name = $1 AND org_id = $2",
                subject_name, org_id
            )

            if existing:
                print(f"SKIP {subject_name}: already exists")
                print()
                continue

            teacher_email = subject_teachers[subject_name]
            teacher_id = teacher_ids.get(teacher_email)

            if not teacher_id:
                print(f"SKIP {subject_name}: teacher {teacher_email} not found")
                print()
                continue

            try:
                async with conn.transaction():
                    subject_id = str(uuid4())
                    now = datetime.utcnow()

                    await conn.execute(
                        """
                        INSERT INTO subjects 
                        (id, name, code, org_id, teacher_id, teacher_name, is_active, credit_hours, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        subject_id, subject_name, code, org_id, None, None, True, 1, now, now
                    )
                    subject_count += 1

                    timetable_rows_for_subject = 0
                    for year in ["Year 10", "Year 11", "Year 12"]:
                        class_id = class_id_map.get(year)
                        if not class_id:
                            print(f"  WARNING {subject_name} + {year}: class not found")
                            continue

                        timetable_id = str(uuid4())

                        await conn.execute(
                            """
                            INSERT INTO timetables
                            (id, class_id, subject_id, day_of_week, start_time, end_time, room, teacher_id, org_id, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            """,
                            timetable_id, class_id, subject_id, -1, "00:00", "00:01", None, teacher_id, org_id, now, now
                        )
                        timetable_count += 1
                        timetable_rows_for_subject += 1

                    print(f"DONE {subject_name} ({code})")
                    print(f"  Subject inserted: {subject_id[:8]}...")
                    print(f"  Timetable rows: {timetable_rows_for_subject} (Year 10, 11, 12 -> {teacher_email})")
                    print()

            except Exception as e:
                print(f"FAILED {subject_name}: {e}")
                print()

        print()
        print("=" * 140)
        print("FINAL SUMMARY")
        print("=" * 140)
        print()
        print(f"Subjects created: {subject_count}/6")
        print(f"Timetable rows created: {timetable_count}/18")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
