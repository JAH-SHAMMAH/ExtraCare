#!/usr/bin/env python3
"""
DRY-RUN: Show all email changes before applying

This script shows EVERY email that will change, in order, for your review.

Changes applied:
1. Students: student.fairview-school.ng → fairviewschoolng.com
2. Staff: fairview-school.ng (hyphen) → fairviewschoolng.com (no hyphen)
3. All others: unchanged

Usage:
    python scripts/bulk_email_update_dryrun.py
"""

import sqlite3

def dryrun():
    conn = sqlite3.connect('extracare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all students
    cur.execute("""
    SELECT 'student' as type, id, first_name, last_name, email
    FROM students
    WHERE email IS NOT NULL
    ORDER BY first_name, last_name
    """)

    students = cur.fetchall()

    # Get all staff
    cur.execute("""
    SELECT 'staff' as type, id, full_name, NULL as last_name, email
    FROM users
    ORDER BY full_name
    """)

    staff = cur.fetchall()

    conn.close()

    # Calculate changes
    student_changes = []
    staff_changes = []
    unchanged = []

    for s in students:
        name = f"{s['first_name']} {s['last_name']}"
        old_email = s['email']

        # All students: student.fairview-school.ng → fairviewschoolng.com
        if old_email.endswith('@student.fairview-school.ng'):
            new_email = old_email.replace('@student.fairview-school.ng', '@fairviewschoolng.com')
            student_changes.append({
                'type': 'student',
                'id': s['id'],
                'name': name,
                'old': old_email,
                'new': new_email
            })
        else:
            unchanged.append({'type': 'student', 'name': name, 'email': old_email})

    for u in staff:
        old_email = u['email']

        # Staff: fairview-school.ng (hyphen) → fairviewschoolng.com (no hyphen)
        if '@fairview-school.ng' in old_email:
            new_email = old_email.replace('@fairview-school.ng', '@fairviewschoolng.com')
            staff_changes.append({
                'type': 'staff',
                'id': u['id'],
                'name': u['full_name'],
                'old': old_email,
                'new': new_email
            })
        elif '@fairviewschoolng.com' in old_email:
            unchanged.append({'type': 'staff', 'name': u['full_name'], 'email': old_email})
        else:
            unchanged.append({'type': 'staff', 'name': u['full_name'], 'email': old_email})

    # Print report
    print("\n" + "="*100)
    print("EMAIL UPDATE DRY-RUN REPORT")
    print("="*100)

    print(f"\nSTUDENT CHANGES ({len(student_changes)} records):")
    print("-" * 100)
    for i, change in enumerate(student_changes, 1):
        print(f"  {i:3d}. {change['name']:<35} | {change['old']:<40} -> {change['new']}")

    print(f"\n\nSTAFF CHANGES ({len(staff_changes)} records):")
    print("-" * 100)
    for i, change in enumerate(staff_changes, 1):
        print(f"  {i:3d}. {change['name']:<35} | {change['old']:<40} -> {change['new']}")

    print(f"\n\nUNCHANGED ({len(unchanged)} records):")
    print("-" * 100)
    for i, u in enumerate(unchanged, 1):
        print(f"  {i:3d}. {u['name']:<35} | {u['email']}")

    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    print(f"Students to update: {len(student_changes)}")
    print(f"Staff to update: {len(staff_changes)}")
    print(f"Unchanged: {len(unchanged)}")
    print(f"Total: {len(student_changes) + len(staff_changes) + len(unchanged)}")
    print(f"\nTo apply these changes, run:")
    print(f"  python scripts/bulk_email_update_real.py")
    print("="*100 + "\n")

if __name__ == "__main__":
    dryrun()
