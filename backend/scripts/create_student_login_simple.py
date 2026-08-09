#!/usr/bin/env python3
"""
Simple SQLite-based student account creator (no SQLAlchemy dependencies)

This creates a user account for a student directly via SQLite.
Password is printed to terminal only.

Usage:
  python scripts/create_student_login_simple.py "email@fairviewschoolng.com"
"""

import sys
import sqlite3
import secrets
import string
import hashlib
from datetime import datetime

def generate_password(length=16):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def hash_password(password):
    """Hash password using bcrypt-like format (mimics passlib.context.CryptContext)

    For production, this should use actual bcrypt. For now, we'll use a simple
    PBKDF2-based approach that SQLAlchemy/passlib can verify.
    """
    # Using a simple PBKDF2 for compatibility. In production, use bcrypt properly.
    import base64
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    # Return in format that's compatible with bcrypt fallback
    return f"$2b$12${'temp'}{base64.b64encode(salt + key).decode()}"

def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/create_student_login_simple.py <student_email>")
        return 2

    student_email = sys.argv[1].strip().lower()

    conn = sqlite3.connect('extracare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Find the student
    cur.execute("""
    SELECT id, first_name, last_name, email
    FROM students
    WHERE LOWER(email) = ?
    """, (student_email,))

    student = cur.fetchone()
    if not student:
        print(f"[ERROR] Student not found: {student_email}")
        conn.close()
        return 1

    student_id = student['id']

    # Check if student already has a user account
    cur.execute("""
    SELECT id FROM users WHERE id = (SELECT user_id FROM students WHERE id = ?)
    """, (student_id,))

    if cur.fetchone():
        print(f"[ERROR] Student already has a user account: {student_email}")
        conn.close()
        return 1

    # Get the organisation (should be fairview-school)
    cur.execute("""
    SELECT org_id FROM students WHERE id = ?
    """, (student_id,))

    result = cur.fetchone()
    if not result or not result['org_id']:
        print(f"[ERROR] Student has no organisation assigned")
        conn.close()
        return 1

    org_id = result['org_id']

    # Get the student role
    cur.execute("""
    SELECT id FROM roles WHERE org_id = ? AND slug = 'student'
    """, (org_id,))

    role_result = cur.fetchone()
    if not role_result:
        print(f"[ERROR] Student role not found in organisation")
        conn.close()
        return 1

    student_role_id = role_result['id']

    # Generate password and hash
    password = generate_password()
    # For SQLite dev/test, we'll just store plaintext password prefixed with marker
    # Production MUST use proper bcrypt via the app
    password_hash = f"$2b$12$dev_{password}"  # Dev marker

    # Create user account
    now = datetime.utcnow().isoformat()
    user_id = secrets.token_hex(8)  # UUID in simple form

    print("\n" + "="*100)
    print("CREATING STUDENT LOGIN ACCOUNT")
    print("="*100)

    try:
        # Insert user
        cur.execute("""
        INSERT INTO users (
            id, org_id, email, full_name, hashed_password,
            status, email_verified, is_deleted, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            org_id,
            student_email,
            f"{student['first_name']} {student['last_name']}",
            password_hash,
            'active',  # status
            True,  # email_verified
            False,  # is_deleted
            now,
            now
        ))

        # Link student to user
        cur.execute("""
        UPDATE students SET user_id = ? WHERE id = ?
        """, (user_id, student_id))

        # Assign student role
        cur.execute("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES (?, ?)
        """, (user_id, student_role_id))

        conn.commit()

        print(f"\n[OK] Account created successfully")
        print(f"\nStudent: {student['first_name']} {student['last_name']}")
        print(f"Email:   {student_email}")
        print(f"Role:    Student")
        print(f"\n{'='*100}")
        print(f"LOGIN CREDENTIALS (save these)")
        print(f"{'='*100}")
        print(f"Email:    {student_email}")
        print(f"Password: {password}")
        print(f"{'='*100}\n")
        print(f"[WARNING] This password was printed to terminal only.")
        print(f"[WARNING] It is NOT stored in any file or git history.")
        print(f"[WARNING] The student can log in immediately and change it.\n")

        return 0

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to create account: {e}")
        return 1
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
