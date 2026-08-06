#!/usr/bin/env python3
"""
Audit teacher accounts: identify dead accounts vs active ones by foreign key references.
Shows @fairview-school.ng vs @fairviewschoolng.com duplicates and gmail accounts.

Usage:
  python audit_teacher_accounts.py <DATABASE_URL>

Example:
  python audit_teacher_accounts.py "postgresql://user:pass@host:5432/school_db_onyz?ssl=require"
"""

import sys
import asyncio
import asyncpg
from urllib.parse import urlparse, parse_qs

async def connect_db(db_url: str):
    """Connect to DB, stripping ?ssl=require from URL and passing ssl='require' separately."""
    # Parse URL and remove ssl=require query param
    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query)

    # Remove ssl param from query string
    query_params.pop('ssl', None)

    # Reconstruct URL without ssl param
    clean_url = db_url.split('?')[0]

    # Connect with ssl='require' passed as kwarg
    conn = await asyncpg.connect(clean_url, ssl='require')
    return conn

async def count_fk_references(conn, user_id: int) -> dict:
    """Count all foreign key references for a user across the database."""
    counts = {
        "school_classes": 0,
        "subjects": 0,
        "teacher_sections": 0,
        "lesson_plans": 0,
        "timetable_entries": 0,
        "assessments": 0,
    }

    # school_classes where teacher_id
    counts["school_classes"] = await conn.fetchval(
        "SELECT COUNT(*) FROM school_classes WHERE teacher_id = $1", user_id
    ) or 0

    # subjects where teacher_id
    counts["subjects"] = await conn.fetchval(
        "SELECT COUNT(*) FROM subjects WHERE teacher_id = $1", user_id
    ) or 0

    # teacher_sections
    counts["teacher_sections"] = await conn.fetchval(
        "SELECT COUNT(*) FROM teacher_sections WHERE teacher_id = $1", user_id
    ) or 0

    # lesson_plans where teacher_id
    counts["lesson_plans"] = await conn.fetchval(
        "SELECT COUNT(*) FROM lesson_plans WHERE teacher_id = $1", user_id
    ) or 0

    # timetable entries (if exists)
    try:
        counts["timetable_entries"] = await conn.fetchval(
            "SELECT COUNT(*) FROM timetable WHERE teacher_id = $1", user_id
        ) or 0
    except:
        pass

    # assessments where teacher_id
    try:
        counts["assessments"] = await conn.fetchval(
            "SELECT COUNT(*) FROM assessments WHERE teacher_id = $1", user_id
        ) or 0
    except:
        pass

    return counts

def has_data(counts: dict) -> bool:
    """Check if user has any linked data."""
    return sum(counts.values()) > 0

async def main():
    if len(sys.argv) < 2:
        print("Usage: python audit_teacher_accounts.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]

    try:
        conn = await connect_db(db_url)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    try:
        print("=" * 100)
        print("1. AUDIT: @fairview-school.ng ACCOUNTS (potential dead data)")
        print("=" * 100)

        # Get all @fairview-school.ng accounts
        old_domain_accounts = await conn.fetch("""
            SELECT
                id,
                email,
                full_name,
                job_title,
                created_at
            FROM users
            WHERE email ILIKE '%@fairview-school.ng'
            AND job_title ILIKE '%teacher%'
            ORDER BY email
        """)

        old_domain_active = 0

        if not old_domain_accounts:
            print("\n✓ No @fairview-school.ng accounts found")
        else:
            print(f"\nFound {len(old_domain_accounts)} @fairview-school.ng accounts:\n")

            for account in old_domain_accounts:
                fk_refs = await count_fk_references(conn, account['id'])
                has_linked_data = has_data(fk_refs)

                if has_linked_data:
                    old_domain_active += 1

                print(f"Email:  {account['email']}")
                print(f"Name:   {account['full_name']}")
                print(f"Role:   {account['job_title']}")
                print(f"Created: {account['created_at'].date()}")
                print(f"Linked data: {'YES ⚠️' if has_linked_data else 'NONE (dead account)'}")

                if has_linked_data:
                    details = [f"{k}: {v}" for k, v in fk_refs.items() if v > 0]
                    print(f"  References: {', '.join(details)}")

                # Try to find matching @fairviewschoolng.com account
                subject_match = account['email'].split('@')[0]
                matching = await conn.fetchrow("""
                    SELECT id, email, full_name, created_at
                    FROM users
                    WHERE email ILIKE $1 || '%@fairviewschoolng.com'
                    AND job_title ILIKE '%teacher%'
                """, subject_match)

                if matching:
                    match_refs = await count_fk_references(conn, matching['id'])
                    match_has_data = has_data(match_refs)
                    print(f"  Matching .com account: {matching['email']}")
                    print(f"    Linked data: {'YES' if match_has_data else 'NONE'}")
                    if match_has_data:
                        details = [f"{k}: {v}" for k, v in match_refs.items() if v > 0]
                        print(f"    References: {', '.join(details)}")
                else:
                    print(f"  Matching .com account: NONE FOUND")

                print()

        print("\n" + "=" * 100)
        print("2. AUDIT: GMAIL ACCOUNTS (personal emails, not @fairviewschoolng.com)")
        print("=" * 100)

        # Get all gmail/personal accounts
        gmail_accounts = await conn.fetch("""
            SELECT
                id,
                email,
                full_name,
                job_title,
                created_at
            FROM users
            WHERE (job_title ILIKE '%teacher%' OR job_title ILIKE '%head%' OR job_title ILIKE '%coordinator%' OR job_title ILIKE '%officer%')
            AND email NOT ILIKE '%@fairviewschoolng.com'
            AND email NOT ILIKE '%@fairview-school.ng'
            AND email NOT ILIKE '%seed%'
            AND email NOT LIKE 'seed-%'
            ORDER BY email
        """)

        gmail_active = 0

        if not gmail_accounts:
            print("\n✓ No gmail/personal accounts found")
        else:
            print(f"\nFound {len(gmail_accounts)} gmail/personal accounts:\n")

            for account in gmail_accounts:
                fk_refs = await count_fk_references(conn, account['id'])
                has_linked_data = has_data(fk_refs)

                if has_linked_data:
                    gmail_active += 1

                print(f"Email:  {account['email']}")
                print(f"Name:   {account['full_name']}")
                print(f"Role:   {account['job_title']}")
                print(f"Created: {account['created_at'].date()}")
                print(f"Linked data: {'YES ✓' if has_linked_data else 'NONE (dead account)'}")

                if has_linked_data:
                    details = [f"{k}: {v}" for k, v in fk_refs.items() if v > 0]
                    print(f"  References: {', '.join(details)}")

                print()

        print("\n" + "=" * 100)
        print("SUMMARY & RECOMMENDATION")
        print("=" * 100)

        print(f"\n@fairview-school.ng: {len(old_domain_accounts)} accounts")
        print(f"  Active (have linked data): {old_domain_active}")
        print(f"  Dead (no linked data): {len(old_domain_accounts) - old_domain_active}")

        print(f"\nGmail/Personal: {len(gmail_accounts)} accounts")
        print(f"  Active (have linked data): {gmail_active}")
        print(f"  Dead (no linked data): {len(gmail_accounts) - gmail_active}")

        print("\n" + "=" * 100)
        print("SUGGESTED EXCLUSION RULES:")
        print("=" * 100)
        print("""
✗ EXCLUDE ALL @fairview-school.ng accounts
  → Login domain gate blocks them anyway (not @fairviewschoolng.com)
  → Whether active or dead, they cannot log in

✗ EXCLUDE gmail/personal accounts with NO linked data
  → Dead test accounts, not needed

✓ KEEP gmail/personal accounts with linked data
  → These are real logins on a different domain, need auth working
""")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())