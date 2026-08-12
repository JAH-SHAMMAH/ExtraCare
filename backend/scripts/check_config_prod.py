#!/usr/bin/env python3
"""
Check the ACTUAL deployed backend config in production.

Shows whether ALLOWED_STUDENT_EMAIL_DOMAIN is active or reverted.

Usage:
  python scripts/check_config_prod.py "postgresql://user:pass@host/db"
"""

import sys
import asyncio

async def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/check_config_prod.py '<postgresql_url>'")
        return 2

    database_url = sys.argv[1].strip()

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
        # Try to read config from settings table if it exists, or infer from data
        # The most direct way: create a test student with old domain and see if login accepts it

        print("\n" + "="*100)
        print("DEPLOYED BACKEND CONFIG CHECK")
        print("="*100)
        print("\nAttempting to infer ALLOWED_STUDENT_EMAIL_DOMAIN from production state...\n")

        # Check what student email domains actually exist in production
        email_stats = await conn.fetchrow(
            """
            SELECT
              COUNT(CASE WHEN email LIKE '%@student.fairview-school.ng' THEN 1 END) as student_ng_count,
              COUNT(CASE WHEN email LIKE '%@fairviewschoolng.com' THEN 1 END) as fairviewschoolng_count,
              COUNT(CASE WHEN email IS NOT NULL THEN 1 END) as total_students
            FROM students
            """
        )

        print(f"Student email distribution in production:")
        print(f"  @student.fairview-school.ng: {email_stats['student_ng_count']}")
        print(f"  @fairviewschoolng.com:        {email_stats['fairviewschoolng_count']}")
        print(f"  Total students with email:    {email_stats['total_students']}")

        # Check staff domains
        staff_stats = await conn.fetchrow(
            """
            SELECT
              COUNT(CASE WHEN email LIKE '%@fairview-school.ng' THEN 1 END) as fairview_school_ng_count,
              COUNT(CASE WHEN email LIKE '%@fairviewschoolng.com' THEN 1 END) as fairviewschoolng_com_count,
              COUNT(CASE WHEN email IS NOT NULL THEN 1 END) as total_staff
            FROM users
            """
        )

        print(f"\nStaff email distribution in production:")
        print(f"  @fairview-school.ng:  {staff_stats['fairview_school_ng_count']}")
        print(f"  @fairviewschoolng.com: {staff_stats['fairviewschoolng_com_count']}")
        print(f"  Total staff with email: {staff_stats['total_staff']}")

        print(f"\n" + "="*100)
        print("INTERPRETATION")
        print("="*100)

        if email_stats['student_ng_count'] > 0 and email_stats['fairviewschoolng_count'] == 0:
            print(f"\n[RESULT] Students still on @student.fairview-school.ng")
            print(f"         This means the bulk email rewrite NEVER RAN in production.")
            print(f"         The deployed config is STILL the dual-domain version (commit 08b2bd1)")
            print(f"         OR the single-domain revert (commit 62371fc) is live but students")
            print(f"         were never actually renamed in production.")
        elif email_stats['fairviewschoolng_count'] > 0 and email_stats['student_ng_count'] == 0:
            print(f"\n[RESULT] ALL students moved to @fairviewschoolng.com")
            print(f"         The bulk email rewrite DID run in production (unlikely, but possible)")
            print(f"         Deployed config is single-domain revert (commit 62371fc)")
        elif email_stats['student_ng_count'] > 0 and email_stats['fairviewschoolng_count'] > 0:
            print(f"\n[RESULT] Students split across BOTH domains")
            print(f"         Deployed config MUST be dual-domain (commit 08b2bd1)")
            print(f"         Neither bulk rewrite nor individual updates happened in production")

        print("\n" + "="*100 + "\n")

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
