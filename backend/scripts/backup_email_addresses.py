#!/usr/bin/env python3
"""
BACKUP: Export current email addresses before bulk update

This script exports ALL student and staff email addresses as they exist RIGHT NOW
to a local CSV file (NOT committed to git). Use this if any updates need to be
reversed.

Usage:
    python scripts/backup_email_addresses.py

Output:
    email_backup_TIMESTAMP.csv (in the scripts directory)
"""

import sqlite3
import csv
from datetime import datetime

def backup_emails():
    conn = sqlite3.connect('extracare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all student emails
    cur.execute("""
    SELECT 'student' as type, id, first_name, last_name, email
    FROM students
    WHERE email IS NOT NULL
    ORDER BY first_name, last_name
    """)

    students = cur.fetchall()

    # Get all staff/user emails
    cur.execute("""
    SELECT 'staff' as type, id, full_name, NULL as last_name, email
    FROM users
    ORDER BY full_name
    """)

    staff = cur.fetchall()

    conn.close()

    # Write to CSV (in backend root, not scripts dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"email_backup_{timestamp}.csv"

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['type', 'id', 'name', 'current_email', 'backup_timestamp'])

        for s in students:
            writer.writerow([
                s['type'],
                s['id'],
                f"{s['first_name']} {s['last_name']}",
                s['email'],
                timestamp
            ])

        for u in staff:
            writer.writerow([
                u['type'],
                u['id'],
                u['full_name'],
                u['email'],
                timestamp
            ])

    print(f"\n{'='*80}")
    print(f"BACKUP COMPLETE")
    print(f"{'='*80}")
    print(f"\nFile: {filename}")
    print(f"Location: {script_dir}/{filename}")
    print(f"\nContents:")
    print(f"  Students: {len(students)}")
    print(f"  Staff: {len(staff)}")
    print(f"  Total: {len(students) + len(staff)}")
    print(f"\n** WARNING **  KEEP THIS FILE SAFE - it's the only restore point if updates need reversal")
    print(f"** WARNING **  DO NOT COMMIT TO GIT - this is a local backup only")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.dirname(script_dir))  # cd to backend root
    backup_emails()
