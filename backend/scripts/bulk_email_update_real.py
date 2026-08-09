#!/usr/bin/env python3
"""
REAL: Apply email domain normalization to students and principal only

This script applies ACTUAL email changes to the database.
Dead .ng accounts (10 subject teachers with zero linked data) are EXCLUDED.
Only 490 students + 1 principal (Dr. Adeyemi Okafor / principal@fairview-school.ng) are updated.

BACKUP FIRST:
    python scripts/backup_email_addresses.py

DRY-RUN FIRST:
    python scripts/bulk_email_update_dryrun.py

THEN APPLY:
    python scripts/bulk_email_update_real.py

Changes applied:
1. Students: student.fairview-school.ng → fairviewschoolng.com
2. Principal ONLY: principal@fairview-school.ng → fairviewschoolng.com
3. 10 dead .ng subject teachers: EXCLUDED (no changes)
4. All others: unchanged

Usage:
    python scripts/bulk_email_update_real.py
"""

import sqlite3
from datetime import datetime

def apply_updates():
    conn = sqlite3.connect('extracare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Dead .ng accounts to EXCLUDE (zero linked data)
    DEAD_ACCOUNTS = {
        'ict@fairview-school.ng',
        'chemistry@fairview-school.ng',
        'geography@fairview-school.ng',
        'mathematics@fairview-school.ng',
        'economics@fairview-school.ng',
        'english@fairview-school.ng',
        'crs@fairview-school.ng',
        'physics@fairview-school.ng',
        'biology@fairview-school.ng',
        'government@fairview-school.ng',
    }

    print("\n" + "="*100)
    print("EMAIL UPDATE - REAL WRITE")
    print("="*100)

    # Get all students
    cur.execute("""
    SELECT id, first_name, last_name, email
    FROM students
    WHERE email IS NOT NULL
    ORDER BY first_name, last_name
    """)
    students = cur.fetchall()

    # Get all staff
    cur.execute("""
    SELECT id, full_name, email
    FROM users
    ORDER BY full_name
    """)
    staff = cur.fetchall()

    student_updates = []
    staff_updates = []
    excluded = []

    # Process students
    for s in students:
        if s['email'].endswith('@student.fairview-school.ng'):
            new_email = s['email'].replace('@student.fairview-school.ng', '@fairviewschoolng.com')
            student_updates.append((new_email, s['id']))

    # Process staff - ONLY principal, EXCLUDE dead .ng accounts
    for u in staff:
        # Skip if in dead accounts list
        if u['email'] in DEAD_ACCOUNTS:
            excluded.append(u['email'])
            continue

        # Update principal ONLY
        if u['email'] == 'principal@fairview-school.ng':
            new_email = u['email'].replace('@fairview-school.ng', '@fairviewschoolng.com')
            staff_updates.append((new_email, u['id']))

    # Apply updates to students table
    print(f"\nUpdating {len(student_updates)} student emails...")
    for i, (new_email, student_id) in enumerate(student_updates, 1):
        cur.execute("UPDATE students SET email = ? WHERE id = ?", (new_email, student_id))
        if i % 50 == 0:
            print(f"  {i}/{len(student_updates)}...")

    # Apply updates to users table (staff)
    print(f"Updating {len(staff_updates)} staff emails...")
    for new_email, user_id in staff_updates:
        cur.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, user_id))

    # Commit all changes
    conn.commit()
    conn.close()

    # Print summary
    print("\n" + "="*100)
    print("RESULTS")
    print("="*100)
    print(f"[OK] Students updated: {len(student_updates)}")
    print(f"[OK] Staff updated: {len(staff_updates)}")
    print(f"[SKIP] Dead .ng accounts EXCLUDED: {len(excluded)}")
    print(f"\nExcluded (not modified):")
    for email in sorted(excluded):
        print(f"  - {email}")
    print(f"\nTotal records modified: {len(student_updates) + len(staff_updates)}")
    print("="*100 + "\n")

if __name__ == "__main__":
    apply_updates()
