#!/usr/bin/env python3
"""
Audit: TeacherSection schema and seed-classteacher reference case.
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
        print("Usage: python audit_teacher_sections_schema.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 140)
        print("AUDIT: TeacherSection Schema & seed-classteacher Reference")
        print("=" * 140)
        print()

        print("1. SCHEMA: teacher_sections columns")
        print("-" * 140)
        print()

        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'teacher_sections'
            ORDER BY ordinal_position
        """)

        print("teacher_sections columns:")
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  {col['column_name']:20} {col['data_type']:20} {nullable}")

        has_name_column = any(c['column_name'] == 'name' for c in columns)
        print()
        if has_name_column:
            print("teacher_sections HAS a name column (free-text storage)")
        else:
            print("teacher_sections has NO name column (name comes via JOIN to school_sections)")

        print()
        print("2. REFERENCE CASE: seed-classteacher's TeacherSection row(s)")
        print("-" * 140)
        print()

        seed_user = await conn.fetchrow(
            "SELECT id, email FROM users WHERE email ILIKE '%seed%classteacher%' LIMIT 1"
        )

        if not seed_user:
            print("seed-classteacher not found in database")
        else:
            print(f"Found: {seed_user['email']} (id: {str(seed_user['id'])[:8]}...)")
            print()

            ts_rows = await conn.fetch(
                """
                SELECT ts.section_id, ss.name as section_name
                FROM teacher_sections ts
                LEFT JOIN school_sections ss ON ts.section_id = ss.id
                WHERE ts.teacher_id = $1
                """,
                seed_user['id']
            )

            if ts_rows:
                print(f"TeacherSection row(s) for seed-classteacher ({len(ts_rows)} total):")
                for ts in ts_rows:
                    print(f"  section_id: {str(ts['section_id'])[:8]}...")
                    print(f"  section_name (from school_sections): {ts['section_name']}")
                print()
                print(f"Section name used: {ts_rows[0]['section_name']}")
            else:
                print("seed-classteacher has ZERO TeacherSection rows")
                print("(Yet Secondary School Report works - how?)")

        print()
        print("3. SCHOOL_SECTIONS INVENTORY")
        print("-" * 140)
        print()

        sections = await conn.fetch("SELECT id, name FROM school_sections ORDER BY name")
        print(f"school_sections rows ({len(sections)} total):")
        for s in sections:
            print(f"  {s['name']:20} (id: {str(s['id'])[:8]}...)")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
