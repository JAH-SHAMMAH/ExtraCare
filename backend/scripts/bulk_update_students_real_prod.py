#!/usr/bin/env python3
"""
REAL WRITE: Apply email domain changes in PRODUCTION.

This connects to school_db_onyz via the postgresql:// URL passed as an argument,
verified against production, not local SQLite.

IMPORTANT: Run backup and dry-run FIRST.

Changes applied:
  1. Students: student.fairview-school.ng → fairviewschoolng.com
  2. All others: unchanged

Usage:
  python scripts/bulk_update_students_real_prod.py "postgresql://user:pass@host/db"
"""

import sys
import asyncio

async def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/bulk_update_students_real_prod.py '<postgresql_url>'")
        return 2

    database_url = sys.argv[1].strip().split("?")[0]

    try:
        import asyncpg
    except ImportError:
        print("[ERROR] asyncpg not installed. Run: pip install asyncpg")
        return 1

    try:
        conn = await asyncpg.connect(database_url, ssl="require")
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return 1

    try:
        # Fetch all students with emails that need changing
        rows = await conn.fetch(
            """
            SELECT id, first_name, last_name, email
            FROM students
            WHERE email IS NOT NULL
              AND email LIKE '%@student.fairview-school.ng'
            ORDER BY first_name, last_name
            """
        )

        if not rows:
            print("[INFO] No students found with @student.fairview-school.ng emails")
            print("[INFO] All students may already be on @fairviewschoolng.com")
            return 0

        print("\n" + "="*100)
        print("EMAIL UPDATE - PRODUCTION WRITE")
        print("="*100)
        print(f"\nUpdating {len(rows)} student emails...\n")

        async with conn.transaction():
            for i, row in enumerate(rows, 1):
                old_email = row['email']
                new_email = old_email.replace('@student.fairview-school.ng', '@fairviewschoolng.com')

                await conn.execute(
                    "UPDATE students SET email = $1 WHERE id = $2",
                    new_email, row['id']
                )

                if i % 50 == 0 or i == len(rows):
                    print(f"  {i}/{len(rows)}...")

        print("\n" + "="*100)
        print("RESULTS")
        print("="*100)
        print(f"[OK] {len(rows)} student emails updated")
        print(f"     @student.fairview-school.ng → @fairviewschoolng.com")
        print("="*100 + "\n")

        return 0

    except Exception as e:
        print(f"[ERROR] Update failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
