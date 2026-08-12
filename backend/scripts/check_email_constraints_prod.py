#!/usr/bin/env python3
import sys
import asyncio

async def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/check_email_constraints_prod.py '<postgresql_url>'")
        return 2

    database_url = sys.argv[1].strip().split("?")[0]

    import asyncpg

    conn = await asyncpg.connect(database_url, ssl="require")

    try:
        constraint = await conn.fetchval(
            """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'students' AND constraint_type = 'UNIQUE'
              AND constraint_name LIKE '%email%'
            """
        )

        print("\n" + "="*100)
        print("SCHEMA CHECK: Email Uniqueness")
        print("="*100)

        if constraint:
            print(f"\n[CONSTRAINT FOUND] {constraint}")
            print("Email MUST be unique on students table - duplicates will FAIL")
        else:
            print(f"\n[NO CONSTRAINT] Email is NOT unique on students table")
            print("Duplicates are ALLOWED but will cause login ambiguity")

        dupes = await conn.fetch(
            """
            SELECT
              CASE
                WHEN email LIKE '%@student.fairview-school.ng'
                THEN REPLACE(email, '@student.fairview-school.ng', '@fairviewschoolng.com')
                ELSE email
              END as new_email,
              COUNT(*) as count,
              STRING_AGG(first_name || ' ' || last_name, ', ' ORDER BY first_name) as names,
              STRING_AGG(id::text, ', ' ORDER BY first_name) as ids
            FROM students
            WHERE email IS NOT NULL
            GROUP BY new_email
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            """
        )

        print(f"\n" + "="*100)
        print("DUPLICATE EMAILS (after transformation)")
        print("="*100)

        if not dupes:
            print("\n[GOOD] No duplicate emails after transformation")
        else:
            print(f"\nFound {len(dupes)} email addresses that will be duplicated:\n")
            for row in dupes:
                print(f"Email: {row['new_email']}")
                print(f"  Count: {row['count']}")
                print(f"  Names: {row['names']}")
                print(f"  IDs: {row['ids']}")
                print()

        return 0

    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
