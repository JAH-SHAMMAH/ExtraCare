#!/usr/bin/env python3
"""
DRY-RUN (CORRECTED): Teacher assignments with explicit subject matching.
Excludes [SEED]-prefixed records. Warns on EVERY unmatched teacher upfront.

Usage:
  python assign_teachers_dryrun.py <DATABASE_URL>
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
        print("Usage: python assign_teachers_dryrun.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 140)
        print("DRY-RUN: Teacher Assignment Plan")
        print("=" * 140)
        print()

        # EXPLICIT subject mapping: teacher email → exact subject name (as it appears in DB)
        subject_mapping = {
            "biology@fairviewschoolng.com": "Biology",
            "chemistry@fairviewschoolng.com": "Chemistry",
            "crs@fairviewschoolng.com": "Christian Religious Studies",
            "economics@fairviewschoolng.com": "Economics",
            "english@fairviewschoolng.com": "English Language",
            "geography@fairviewschoolng.com": "Geography",
            "government@fairviewschoolng.com": "Government",
            "ict@fairviewschoolng.com": "Computer Studies / ICT",
            "mathematics@fairviewschoolng.com": "Mathematics",
            "physics@fairviewschoolng.com": "Physics",
        }

        # Class-teacher assignments (6 class teachers)
        class_assignments = {
            "Nursery": "geography@fairviewschoolng.com",
            "Year 1": "english@fairviewschoolng.com",
            "Year 6": "mathematics@fairviewschoolng.com",
            "Year 7": "ict@fairviewschoolng.com",
            "Year 9": "chemistry@fairviewschoolng.com",
            "Year 11": "economics@fairviewschoolng.com",
        }

        # Get teacher IDs for mapping
        teacher_ids = {}
        for email in subject_mapping.keys():
            teacher_id = await conn.fetchval(
                "SELECT id FROM users WHERE email = $1",
                email
            )
            if teacher_id:
                teacher_ids[email] = teacher_id

        print("=" * 140)
        print("SUBJECT MATCH CHECK (before assignment)")
        print("=" * 140)
        print()

        # Get all subjects (exclude [SEED]-prefixed — names starting with bracket)
        all_subjects = await conn.fetch("""
            SELECT id, name, teacher_id FROM subjects 
            WHERE NOT name LIKE '[SEED]%'
            ORDER BY name
        """)

        actual_subject_names = {s["name"] for s in all_subjects}

        matched_emails = set()
        for email, expected_name in subject_mapping.items():
            if expected_name in actual_subject_names:
                matched_emails.add(email)
                print(f"✓ {email}: '{expected_name}' found")
            else:
                print(f"❌ WARNING: {email}: '{expected_name}' NOT FOUND in database")

        print()
        if len(matched_emails) < len(subject_mapping):
            missing_count = len(subject_mapping) - len(matched_emails)
            print(f"⚠️  {missing_count} subjects MISSING — they must be CREATED before assignment")
            print()

        print()
        print("=" * 140)
        print("1. SUBJECT ASSIGNMENTS (10 teachers → their subjects)")
        print("=" * 140)
        print()

        for subject in all_subjects:
            current_teacher_id = subject["teacher_id"]
            current_email = ""
            if current_teacher_id:
                current_email = await conn.fetchval(
                    "SELECT email FROM users WHERE id = $1",
                    current_teacher_id
                ) or ""

            # Find which email (if any) should be assigned to this subject
            assigned_email = None
            for email, subject_name in subject_mapping.items():
                if subject_name == subject["name"]:
                    assigned_email = email
                    break

            if assigned_email:
                new_teacher_id = teacher_ids.get(assigned_email)
                status = "ASSIGN"
                if new_teacher_id == current_teacher_id:
                    status = "✓ (already assigned)"
            else:
                new_teacher_id = None
                status = "LEAVE NULL"
                if current_teacher_id is None:
                    status = "✓ (already null)"

            print(f"{subject['name']}")
            print(f"  Current: {current_email if current_email else 'NULL'}")
            print(f"  New:     {assigned_email if assigned_email else 'NULL'} — {status}")
            print()

        print()
        print("=" * 140)
        print("2. CLASS-TEACHER ASSIGNMENTS (16 total: 6 assigned, 10 cleared to NULL)")
        print("=" * 140)
        print()

        # Get all classes (exclude [SEED]-prefixed — names starting with bracket)
        all_classes = await conn.fetch("""
            SELECT id, name, teacher_id FROM school_classes 
            WHERE NOT name LIKE '[SEED]%'
            ORDER BY name
        """)

        for cls in all_classes:
            assigned_email = class_assignments.get(cls["name"])

            current_teacher_id = cls["teacher_id"]
            current_email = ""
            if current_teacher_id:
                current_email = await conn.fetchval(
                    "SELECT email FROM users WHERE id = $1",
                    current_teacher_id
                ) or ""

            if assigned_email:
                new_teacher_id = teacher_ids.get(assigned_email)
                status = "ASSIGN"
                if new_teacher_id == current_teacher_id:
                    status = "✓ (already assigned)"
            else:
                new_teacher_id = None
                status = "CLEAR TO NULL"
                if current_teacher_id is None:
                    status = "✓ (already null)"

            print(f"{cls['name']}")
            print(f"  Current: {current_email if current_email else 'NULL'}")
            print(f"  New:     {assigned_email if assigned_email else 'NULL'} — {status}")
            print()

        print()
        print("=" * 140)
        print("SUMMARY")
        print("=" * 140)
        print()
        print(f"Subjects matched: {len(matched_emails)}/10")
        if len(matched_emails) < 10:
            missing = len(subject_mapping) - len(matched_emails)
            print(f"Subjects MISSING (must create): {missing}")
            for email, name in subject_mapping.items():
                if email not in matched_emails:
                    print(f"  - {name}")
        print(f"Class-teacher assignments: 6 teachers assigned as form teachers")
        print(f"Classes cleared to NULL: 10 (currently pointing to dead principal@fairview-school.ng)")
        print(f"[SEED]-prefixed records: EXCLUDED from this assignment pass")
        print()

        if len(matched_emails) < len(subject_mapping):
            print("❌ BLOCKER: Missing subjects must be created before proceeding.")
        else:
            print("✓ All subjects matched. Ready for REAL version.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
