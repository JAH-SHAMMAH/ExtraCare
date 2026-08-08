#!/usr/bin/env python3
"""
REAL WRITE: Assign 4 teachers to confirmed subjects, assign 6 class teachers, clear 10 classes.
Atomic per-record: each update wraps in its own transaction.

Usage:
  python assign_teachers_real.py <DATABASE_URL>

Example:
  python assign_teachers_real.py "postgresql://user:pass@host:5432/school_db_onyz?ssl=require"
"""

import sys
import asyncio
import asyncpg
from datetime import datetime

async def connect_db(db_url: str):
    clean_url = db_url.split('?')[0]
    conn = await asyncpg.connect(clean_url, ssl='require')
    return conn

async def main():
    if len(sys.argv) < 2:
        print("Usage: python assign_teachers_real.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 140)
        print("REAL WRITE: Teacher Assignments (Step 1 — 4 subjects + 6 class teachers + 10 class clears)")
        print("=" * 140)
        print()

        # Subject assignments (ONLY the 4 confirmed matches)
        subject_mapping = {
            "crs@fairviewschoolng.com": "Christian Religious Studies",
            "english@fairviewschoolng.com": "English Language",
            "ict@fairviewschoolng.com": "Computer Studies / ICT",
            "mathematics@fairviewschoolng.com": "Mathematics",
        }

        # Class-teacher assignments (6 form teachers)
        class_assignments = {
            "Nursery": "geography@fairviewschoolng.com",
            "Year 1": "english@fairviewschoolng.com",
            "Year 6": "mathematics@fairviewschoolng.com",
            "Year 7": "ict@fairviewschoolng.com",
            "Year 9": "chemistry@fairviewschoolng.com",
            "Year 11": "economics@fairviewschoolng.com",
        }

        # Get teacher IDs
        teacher_ids = {}
        for email in list(subject_mapping.keys()) + list(set(class_assignments.values())):
            teacher_id = await conn.fetchval(
                "SELECT id FROM users WHERE email = $1",
                email
            )
            if teacher_id:
                teacher_ids[email] = teacher_id

        # Get org_id (assume all records belong to same org)
        org_id = await conn.fetchval("SELECT org_id FROM school_classes LIMIT 1")

        print("=" * 140)
        print("1. SUBJECT ASSIGNMENTS (4 teachers → their subjects)")
        print("=" * 140)
        print()

        subject_update_count = 0
        for email, subject_name in subject_mapping.items():
            teacher_id = teacher_ids.get(email)
            if not teacher_id:
                print(f"❌ {email}: teacher not found, skipping")
                continue

            # Get subject ID
            subject_id = await conn.fetchval(
                "SELECT id FROM subjects WHERE name = $1 AND org_id = $2",
                subject_name, org_id
            )
            if not subject_id:
                print(f"❌ {subject_name}: subject not found, skipping")
                continue

            # Get current state before update
            current_teacher_id = await conn.fetchval(
                "SELECT teacher_id FROM subjects WHERE id = $1",
                subject_id
            )

            try:
                # Atomic transaction per subject
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE subjects SET teacher_id = $1, updated_at = $2 WHERE id = $3",
                        teacher_id,
                        datetime.utcnow(),
                        subject_id
                    )
                subject_update_count += 1
                current_email = ""
                if current_teacher_id:
                    current_email = await conn.fetchval(
                        "SELECT email FROM users WHERE id = $1",
                        current_teacher_id
                    ) or "unknown"

                print(f"✓ {subject_name}")
                print(f"  {email} assigned (was: {current_email if current_email else 'NULL'})")
            except Exception as e:
                print(f"❌ {subject_name}: {e}")

            print()

        print()
        print("=" * 140)
        print("2. CLASS-TEACHER ASSIGNMENTS (6 form teachers)")
        print("=" * 140)
        print()

        class_update_count = 0
        for class_name, teacher_email in class_assignments.items():
            teacher_id = teacher_ids.get(teacher_email)
            if not teacher_id:
                print(f"❌ {class_name}: teacher {teacher_email} not found, skipping")
                continue

            # Get class ID
            class_id = await conn.fetchval(
                "SELECT id FROM school_classes WHERE name = $1 AND org_id = $2",
                class_name, org_id
            )
            if not class_id:
                print(f"❌ {class_name}: class not found, skipping")
                continue

            # Get current state
            current_teacher_id = await conn.fetchval(
                "SELECT teacher_id FROM school_classes WHERE id = $1",
                class_id
            )

            try:
                # Atomic transaction per class
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE school_classes SET teacher_id = $1, updated_at = $2 WHERE id = $3",
                        teacher_id,
                        datetime.utcnow(),
                        class_id
                    )
                class_update_count += 1
                current_email = ""
                if current_teacher_id:
                    current_email = await conn.fetchval(
                        "SELECT email FROM users WHERE id = $1",
                        current_teacher_id
                    ) or "unknown"

                print(f"✓ {class_name}")
                print(f"  {teacher_email} assigned (was: {current_email if current_email else 'NULL'})")
            except Exception as e:
                print(f"❌ {class_name}: {e}")

            print()

        print()
        print("=" * 140)
        print("3. CLASS CLEARS (10 classes → NULL, removing dead principal@fairview-school.ng)")
        print("=" * 140)
        print()

        # Get all classes not in the 6-teacher assignment list, not [SEED]-prefixed
        classes_to_clear = await conn.fetch("""
            SELECT id, name, teacher_id FROM school_classes
            WHERE org_id = $1
            AND NOT name LIKE '[SEED]%'
            AND name NOT IN ('Nursery', 'Year 1', 'Year 6', 'Year 7', 'Year 9', 'Year 11')
            ORDER BY name
        """, org_id)

        clear_count = 0
        for cls in classes_to_clear:
            current_teacher_id = cls["teacher_id"]
            if current_teacher_id is None:
                print(f"✓ {cls['name']}: already NULL (skipped)")
                print()
                continue

            # Get current teacher email
            current_email = await conn.fetchval(
                "SELECT email FROM users WHERE id = $1",
                current_teacher_id
            ) or "unknown"

            try:
                # Atomic transaction per class
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE school_classes SET teacher_id = NULL, updated_at = $1 WHERE id = $2",
                        datetime.utcnow(),
                        cls["id"]
                    )
                clear_count += 1
                print(f"✓ {cls['name']}")
                print(f"  cleared (was: {current_email})")
            except Exception as e:
                print(f"❌ {cls['name']}: {e}")

            print()

        print()
        print("=" * 140)
        print("FINAL SUMMARY")
        print("=" * 140)
        print()
        print(f"✓ Subjects updated: {subject_update_count}/4")
        print(f"✓ Class teachers assigned: {class_update_count}/6")
        print(f"✓ Classes cleared: {clear_count}/10")
        print()
        print("✅ Step 1 complete. Ready for Step 2 (create 6 missing subjects).")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())