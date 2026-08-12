#!/usr/bin/env python3
"""
Read-only diagnostic: Find student in production Postgres by name or email pattern.

Usage:
  python scripts/find_student_prod.py "Abebi Abioye" "postgresql://user:pass@host/db"

Shows:
  - Student ID, name, actual email as stored in production RIGHT NOW
  - Whether they have a linked user_id (login account or not)
  - All matching records (in case of duplicates)
"""

import sys
import asyncio

async def main():
    if len(sys.argv) < 3:
        print("usage: python scripts/find_student_prod.py '<name or email pattern>' '<postgresql_url>'")
        print("")
        print("Example:")
        print("  python scripts/find_student_prod.py 'Abebi Abioye' \\")
        print("    'postgresql://school_db_onyz_user:YkbhMJcvMDVWUmqS0k1kaLF837WclhIK@...'")
        return 2

    search_term = sys.argv[1].strip()
    database_url = sys.argv[2].strip()

    try:
        import asyncpg
    except ImportError:
        print("[ERROR] asyncpg not installed. Run: pip install asyncpg")
        return 1

    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return 1

    try:
        # Search by name OR email pattern
        rows = await conn.fetch(
            """
            SELECT
              id,
              first_name,
              last_name,
              email,
              user_id,
              CASE WHEN user_id IS NOT NULL THEN 'YES' ELSE 'NO' END as has_login
            FROM students
            WHERE
              (LOWER(CONCAT(first_name, ' ', last_name)) LIKE LOWER($1))
              OR (LOWER(email) LIKE LOWER($1))
              OR (LOWER(first_name) LIKE LOWER($1))
              OR (LOWER(last_name) LIKE LOWER($1))
            ORDER BY first_name, last_name
            """,
            f"%{search_term}%"
        )

        print("\n" + "="*120)
        print("PRODUCTION STUDENT SEARCH")
        print("="*120)
        print(f"\nSearch term: '{search_term}'")
        print(f"Records found: {len(rows)}\n")

        if not rows:
            print("[RESULT] No students found matching this search in PRODUCTION")
        else:
            print(f"{'ID':<40} {'Name':<30} {'Email':<50} {'Has Login':<12}")
            print("-" * 120)
            for row in rows:
                name = f"{row['first_name']} {row['last_name']}"
                print(f"{row['id']:<40} {name:<30} {row['email']:<50} {row['has_login']:<12}")

            # If exactly one match, show details
            if len(rows) == 1:
                row = rows[0]
                print(f"\n" + "="*120)
                print("DETAILED VIEW (single match)")
                print("="*120)
                print(f"\nStudent ID:  {row['id']}")
                print(f"Name:        {row['first_name']} {row['last_name']}")
                print(f"Email:       {row['email']}")
                print(f"Has login:   {row['has_login']}")
                if row['user_id']:
                    print(f"user_id:     {row['user_id']}")
                else:
                    print(f"user_id:     NULL (no login account linked)")

        print("\n" + "="*120 + "\n")

        return 0

    except Exception as e:
        print(f"[ERROR] Query failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
