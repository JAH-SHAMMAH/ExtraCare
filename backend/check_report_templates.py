import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@dpg-d9clkl9kh4rs73cv3lq0-a.ohio-postgres.render.com/school_db_onyz",
        ssl="require"
    )
    
    # Get report templates with their sections
    templates = await conn.fetch("""
        SELECT rt.id, rt.section_id, ss.name as section_name, ss.curriculum,
               rt.assessment_mode, rt.ca_weight, rt.exam_weight
        FROM report_templates rt
        JOIN school_sections ss ON rt.section_id = ss.id
        ORDER BY ss.position
    """)
    
    if templates:
        print("Report Templates found:")
        for t in templates:
            print(f"\n  Section: {t['section_name']} (curriculum: {t['curriculum']})")
            print(f"    Assessment mode: {t['assessment_mode']}")
            print(f"    CA weight: {t['ca_weight']}, Exam weight: {t['exam_weight']}")
    else:
        print("NO report templates found - this is a problem!")
    
    # Also check what sections DON'T have templates
    sections = await conn.fetch("""
        SELECT ss.id, ss.name, ss.curriculum
        FROM school_sections ss
        WHERE ss.id NOT IN (SELECT section_id FROM report_templates)
        ORDER BY ss.position
    """)
    
    if sections:
        print("\n\nSections WITHOUT report templates:")
        for s in sections:
            print(f"  {s['name']} (curriculum: {s['curriculum']})")
    
    await conn.close()

asyncio.run(main())
