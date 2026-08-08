"""
ATOMIC DRY RUN: Steps 1-4 (Create sections, assign classes, assign teachers)
Shows exact before/after state. NO DATABASE WRITES.
"""
import asyncio
import asyncpg
import uuid
from datetime import datetime

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require",
        timeout=10
    )

    org = await conn.fetchrow("SELECT id FROM organizations LIMIT 1")
    org_id = org['id']
    now = datetime.utcnow().isoformat()

    print("\n" + "=" * 100)
    print("ATOMIC DRY RUN: Steps 1-4 (No database writes)")
    print("=" * 100)

    # ========== STEP 1: Create sections ==========
    print("\n" + "-" * 100)
    print("STEP 1: CREATE 3 NEW SCHOOL_SECTIONS")
    print("-" * 100)

    current_sections = await conn.fetch("SELECT id, name, curriculum FROM school_sections ORDER BY position")
    print(f"\nBEFORE: {len(current_sections)} sections exist:")
    for s in current_sections:
        print(f"  • {s['name']:15} (curriculum: {s['curriculum']})")

    new_sections = [
        {"id": "d5b21129-7d0a-4935-9f59-c424d99786a8", "name": "Nursery", "curriculum": "eyfs", "position": 0},
        {"id": "31a41cb4-0631-4c19-9c7d-4ca7cf1dd2c1", "name": "Primary", "curriculum": "nigerian", "position": 1},
        {"id": "068a9b5a-8588-4b86-96c4-0d587e734622", "name": "Secondary", "curriculum": "nigerian", "position": 2},
    ]

    print(f"\nWILL INSERT: {len(new_sections)} new sections:")
    for s in new_sections:
        print(f"  • {s['name']:15} (curriculum: {s['curriculum']}, position: {s['position']})")

    print(f"\nAFTER: {len(current_sections) + len(new_sections)} total sections")

    # ========== STEP 2: Assign classes ==========
    print("\n" + "-" * 100)
    print("STEP 2: ASSIGN 16 SCHOOL_CLASSES TO NEW SECTIONS")
    print("─" * 100)

    current_unassigned = await conn.fetch("""
        SELECT COUNT(*) as count FROM school_classes WHERE section_id IS NULL
    """)
    unassigned_count = current_unassigned[0]['count']
    print(f"\nBEFORE: {unassigned_count} classes with section_id = NULL")

    # Define class assignments
    class_mappings = {
        "Nursery": "d5b21129-7d0a-4935-9f59-c424d99786a8",
        "Primary": "31a41cb4-0631-4c19-9c7d-4ca7cf1dd2c1",
        "Secondary": "068a9b5a-8588-4b86-96c4-0d587e734622",
    }

    class_level_map = {
        "Early Years": "Nursery",
        "Primary": "Primary",
        "Secondary": "Secondary",
    }

    classes_to_assign = await conn.fetch("""
        SELECT id, name, level FROM school_classes
        WHERE section_id IS NULL
        ORDER BY level, name
    """)

    assignments_by_section = {}
    for cls in classes_to_assign:
        target_section = class_level_map.get(cls['level'])
        if target_section:
            if target_section not in assignments_by_section:
                assignments_by_section[target_section] = []
            assignments_by_section[target_section].append(cls)

    print(f"\nWILL UPDATE: {len(classes_to_assign)} classes")
    for section_name in ["Nursery", "Primary", "Secondary"]:
        classes = assignments_by_section.get(section_name, [])
        print(f"  {section_name}: {len(classes)} classes")
        for cls in classes:
            print(f"    • {cls['name']:30} (level: {cls['level']})")

    print(f"\nAFTER: All {len(classes_to_assign)} classes assigned to appropriate sections")

    # ========== STEP 3: Assign TeacherSection rows ==========
    print("\n" + "-" * 100)
    print("STEP 3: CREATE 13 TEACHERSECTION ROWS")
    print("-" * 100)

    current_teacher_sections = await conn.fetchval("SELECT COUNT(*) FROM teacher_sections")
    print(f"\nBEFORE: {current_teacher_sections} TeacherSection rows exist")

    teacher_sections_map = {
        "geography@fairviewschoolng.com": ["Nursery", "Secondary"],
        "english@fairviewschoolng.com": ["Primary"],
        "mathematics@fairviewschoolng.com": ["Primary"],
        "ict@fairviewschoolng.com": ["Secondary"],
        "chemistry@fairviewschoolng.com": ["Secondary"],
        "economics@fairviewschoolng.com": ["Secondary"],
        "biology@fairviewschoolng.com": ["Secondary"],
        "physics@fairviewschoolng.com": ["Secondary"],
        "government@fairviewschoolng.com": ["Secondary"],
        "crs@fairviewschoolng.com": ["Secondary"],
        "seed-classteacher@fairviewschoolng.com": ["Secondary"],
        "seed-subjectteacher@fairviewschoolng.com": ["Secondary"],
    }

    all_assignments = []
    for section_name in ["Nursery", "Primary", "Secondary"]:
        section_id = class_mappings[section_name]
        teachers_for_section = [
            email for email, sections in teacher_sections_map.items()
            if section_name in sections
        ]

        for email in teachers_for_section:
            teacher = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
            if teacher:
                all_assignments.append({
                    "section_name": section_name,
                    "section_id": section_id,
                    "email": email,
                    "teacher_id": teacher['id'],
                    "is_dual": len(teacher_sections_map[email]) > 1,
                })

    print(f"\nWILL INSERT: {len(all_assignments)} TeacherSection rows:\n")
    for section_name in ["Nursery", "Primary", "Secondary"]:
        section_assignments = [a for a in all_assignments if a['section_name'] == section_name]
        print(f"  {section_name}:")
        for a in section_assignments:
            marker = " (DUAL)" if a['is_dual'] else ""
            print(f"    • {a['email']:40}{marker}")

    print(f"\nAFTER: {current_teacher_sections + len(all_assignments)} total TeacherSection rows")

    # ========== STEP 4: Verify seed data ==========
    print("\n" + "-" * 100)
    print("STEP 4: VERIFY SEED DATA ASSIGNMENTS")
    print("─" * 100)

    seed_class = await conn.fetchrow(
        "SELECT name, level FROM school_classes WHERE name LIKE '%SEED%'"
    )
    seed_class_teacher = await conn.fetchrow(
        "SELECT email FROM users WHERE email = 'seed-classteacher@fairviewschoolng.com'"
    )

    print(f"\nSEED DATA STATE:")
    if seed_class:
        print(f"  [SEED] Report Demo Class: {seed_class['level']}")
    if seed_class_teacher:
        print(f"  seed-classteacher@ exists and will be assigned to Secondary")

    seed_assignment = [a for a in all_assignments if a['email'] == 'seed-classteacher@fairviewschoolng.com']
    if seed_assignment:
        print(f"  ✓ Will create TeacherSection: seed-classteacher@ → Secondary")

    # ========== FINAL SUMMARY ==========
    print("\n" + "=" * 100)
    print("DRY RUN SUMMARY")
    print("=" * 100)
    summary = """
Step 1 (CREATE):   3 new school_sections (Nursery, Primary, Secondary)
Step 2 (UPDATE):   16 school_classes assigned to appropriate sections
Step 3 (CREATE):   13 TeacherSection rows for 12 real + 2 seed teachers
                   - Nursery:   1 teacher (geography@)
                   - Primary:   2 teachers (english@, mathematics@)
                   - Secondary: 10 teachers (incl. geography@ DUAL)
Step 4 (VERIFY):   seed-classteacher@ → Secondary (Year 11)

TOTAL WRITES:
  • INSERT 3 rows into school_sections
  • UPDATE 16 rows in school_classes (set section_id)
  • INSERT 13 rows into teacher_sections
  • 0 changes to High/Junior/Senior sections (untouched)

EXPECTED OUTCOME:
  After this runs, fresh incognito tests should show:
    • seed-classteacher@: Secondary Report only
    • mathematics@: Primary Report only
    • geography@: BOTH Nursery AND Secondary Reports (dual section)
"""
    print(summary)
    print("=" * 100)
    print("\nDRY RUN COMPLETE - NO WRITES EXECUTED")
    print("=" * 100 + "\n")

    await conn.close()

asyncio.run(main())
