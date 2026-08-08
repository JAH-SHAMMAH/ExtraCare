"""
DRY RUN - STEP 3: Assign TeacherSection rows based on ACTUAL data:
  - Class teacher assignments (school_classes.teacher_id)
  - Subject assignments (subjects.teacher_id)
  - Timetable assignments (timetables.teacher_id)
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
    
    # Section IDs from Step 1
    sections = {
        "Nursery": "d5b21129-7d0a-4935-9f59-c424d99786a8",
        "Primary": "31a41cb4-0631-4c19-9c7d-4ca7cf1dd2c1",
        "Secondary": "068a9b5a-8588-4b86-96c4-0d587e734622",
    }
    
    # Build teacher->section mappings from actual data
    teacher_sections = {
        # Nursery
        "geography@fairviewschoolng.com": ["Nursery", "Secondary"],  # class teacher Nursery + subject Year 10-12
        
        # Primary
        "english@fairviewschoolng.com": ["Primary"],      # class teacher Year 1 + subject org-wide
        "mathematics@fairviewschoolng.com": ["Primary"],  # class teacher Year 6 + subject org-wide
        
        # Secondary (subject/class teachers + Timetable Year 10-12)
        "ict@fairviewschoolng.com": ["Secondary"],        # class teacher Year 7 + subject org-wide
        "chemistry@fairviewschoolng.com": ["Secondary"],  # class teacher Year 9 + subject Timetable Y10-12
        "economics@fairviewschoolng.com": ["Secondary"],  # class teacher Year 11 + subject Timetable Y10-12
        "biology@fairviewschoolng.com": ["Secondary"],    # subject Timetable Year 10-12 only
        "physics@fairviewschoolng.com": ["Secondary"],    # subject Timetable Year 10-12 only
        "government@fairviewschoolng.com": ["Secondary"], # subject Timetable Year 10-12 only
        "crs@fairviewschoolng.com": ["Secondary"],        # subject org-wide (assume secondary-level)
        
        # Seed teachers
        "seed-classteacher@fairviewschoolng.com": ["Secondary"],      # class teacher [SEED] Year 11
        "seed-subjectteacher@fairviewschoolng.com": ["Secondary"],    # subject [SEED] Year 11
    }
    
    print("=" * 100)
    print("DRY RUN - STEP 3: CREATE TEACHERSECTION ROWS")
    print("=" * 100)
    print(f"\nOrganization: {org_id}")
    print(f"Timestamp: {now}\n")
    
    all_assignments = []
    
    # Group by section for clarity
    for section_name in ["Nursery", "Primary", "Secondary"]:
        section_id = sections[section_name]
        teachers_for_section = [
            (email, section_name) 
            for email, section_list in teacher_sections.items() 
            if section_name in section_list
        ]
        
        if teachers_for_section:
            print(f"\n{section_name.upper()} SECTION (id: {section_id})")
            print("-" * 100)
            
            for email, section in teachers_for_section:
                # Get teacher ID
                teacher = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
                if teacher:
                    assignment_id = str(uuid.uuid4())
                    all_assignments.append({
                        "id": assignment_id,
                        "teacher_id": teacher['id'],
                        "teacher_email": email,
                        "section_id": section_id,
                        "section_name": section_name,
                        "org_id": org_id,
                    })
                    
                    marker = " (DUAL)" if len(teacher_sections[email]) > 1 else ""
                    print(f"  {email:40} -> {section_name}{marker}")
                    print(f"    id: {assignment_id}")
    
    print("\n" + "=" * 100)
    print("SUMMARY:")
    print(f"  • Will INSERT {len(all_assignments)} TeacherSection rows")
    print(f"  • Nursery: {len([a for a in all_assignments if a['section_name'] == 'Nursery'])} teachers")
    print(f"  • Primary: {len([a for a in all_assignments if a['section_name'] == 'Primary'])} teachers")
    print(f"  • Secondary: {len([a for a in all_assignments if a['section_name'] == 'Secondary'])} teachers")
    print(f"  • Special cases (DUAL sections): geography@ gets 2 rows (Nursery + Secondary)")
    print("=" * 100)
    
    await conn.close()

asyncio.run(main())
