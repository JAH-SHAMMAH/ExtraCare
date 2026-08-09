#!/usr/bin/env python3
"""
DRY-RUN: Create student login account

This script shows EXACTLY which student account will receive a password,
WITHOUT making any changes. Run this first to audit. Then run
create_student_login_real.py to actually create the account.

Usage: python scripts/create_student_login_dryrun.py <student_email_or_id>

Example (by email):
  python scripts/create_student_login_dryrun.py "zainab.obi@student.fairview-school.ng"

Example (by student ID):
  python scripts/create_student_login_dryrun.py "c22013dc-1509-4d80-80e8-5070240b5fa9"

Example (list Year 6 candidates):
  python scripts/create_student_login_dryrun.py --list-year-6
"""

import sys
import os
import sqlite3
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db():
    return sqlite3.connect('extracare.db')

def list_year_6_candidates():
    """Show all Year 6 students available for account creation."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT s.id, s.first_name, s.last_name, s.email, s.student_id, c.name as class_name
    FROM students s
    LEFT JOIN school_classes c ON s.class_id = c.id
    WHERE c.level = 'Primary' AND c.name = 'Year 6'
      AND s.user_id IS NULL
    ORDER BY s.first_name, s.last_name
    """)

    print("\n" + "="*100)
    print("AVAILABLE YEAR 6 STUDENTS (without user accounts)")
    print("="*100)
    for row in cur.fetchall():
        print(f"  Email: {row['email']:<45} ID: {row['id']:<36}")
        print(f"    Name: {row['first_name']} {row['last_name']}")
        print()

    conn.close()

def dryrun_by_email(email):
    """Show what will be created for student by email."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT s.id, s.first_name, s.last_name, s.email, s.student_id, s.user_id,
           c.name as class_name, o.name as org_name
    FROM students s
    LEFT JOIN school_classes c ON s.class_id = c.id
    LEFT JOIN organizations o ON s.org_id = o.id
    WHERE s.email = ?
    """, (email,))

    student = cur.fetchone()
    conn.close()

    if not student:
        print(f"ERROR: No student found with email '{email}'")
        return False

    if student['user_id']:
        print(f"ERROR: Student already has a user account (user_id={student['user_id']})")
        return False

    print("\n" + "="*100)
    print("DRY-RUN: Student Account Creation")
    print("="*100)
    print(f"\nStudent Details:")
    print(f"  Name:        {student['first_name']} {student['last_name']}")
    print(f"  Email:       {student['email']}")
    print(f"  Student ID:  {student['student_id']}")
    print(f"  Class:       {student['class_name']}")
    print(f"  Org:         {student['org_name']}")
    print(f"  Student DB ID: {student['id']}")

    print(f"\nAccount to be created:")
    print(f"  Email:       {student['email']}")
    print(f"  Password:    [WILL BE RANDOMLY GENERATED — printed to terminal only]")
    print(f"  Role:        Student (auto-created, no manual assignment)")
    print(f"  Linked:      students.user_id -> users.id")

    print(f"\nNOTE: The password will ONLY be printed to terminal during account creation.")
    print(f"      It is NEVER committed to git or stored in any file.")

    print("\n" + "="*100)
    print("To proceed with account creation, run:")
    print(f"  python scripts/create_student_login_real.py \"{email}\"")
    print("="*100 + "\n")

    return True

def dryrun_by_id(student_id):
    """Show what will be created for student by ID."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT s.id, s.first_name, s.last_name, s.email, s.student_id, s.user_id,
           c.name as class_name, o.name as org_name
    FROM students s
    LEFT JOIN school_classes c ON s.class_id = c.id
    LEFT JOIN organizations o ON s.org_id = o.id
    WHERE s.id = ?
    """, (student_id,))

    student = cur.fetchone()
    conn.close()

    if not student:
        print(f"ERROR: No student found with ID '{student_id}'")
        return False

    if student['user_id']:
        print(f"ERROR: Student already has a user account (user_id={student['user_id']})")
        return False

    print("\n" + "="*100)
    print("DRY-RUN: Student Account Creation")
    print("="*100)
    print(f"\nStudent Details:")
    print(f"  Name:        {student['first_name']} {student['last_name']}")
    print(f"  Email:       {student['email']}")
    print(f"  Student ID:  {student['student_id']}")
    print(f"  Class:       {student['class_name']}")
    print(f"  Org:         {student['org_name']}")
    print(f"  Student DB ID: {student['id']}")

    print(f"\nAccount to be created:")
    print(f"  Email:       {student['email']}")
    print(f"  Password:    [WILL BE RANDOMLY GENERATED — printed to terminal only]")
    print(f"  Role:        Student (auto-created, no manual assignment)")
    print(f"  Linked:      students.user_id -> users.id")

    print(f"\nNOTE: The password will ONLY be printed to terminal during account creation.")
    print(f"      It is NEVER committed to git or stored in any file.")

    print("\n" + "="*100)
    print("To proceed with account creation, run:")
    print(f"  python scripts/create_student_login_real.py \"{student['email']}\"")
    print("="*100 + "\n")

    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--list-year-6":
        list_year_6_candidates()
    elif "@" in arg:
        # Treat as email
        success = dryrun_by_email(arg)
        sys.exit(0 if success else 1)
    else:
        # Treat as ID
        success = dryrun_by_id(arg)
        sys.exit(0 if success else 1)
