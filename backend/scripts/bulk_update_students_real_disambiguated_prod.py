#!/usr/bin/env python3
import sys
import asyncio

async def main():
    if len(sys.argv) < 2:
        print("usage: bulk_update_students_real_disambiguated_prod.py '<postgresql_url>'")
        return 2

    database_url = sys.argv[1].strip().split("?")[0]
    import asyncpg
    conn = await asyncpg.connect(database_url, ssl="require")

    try:
        rows = await conn.fetch(
            """
            SELECT id, first_name, last_name, email, created_at
            FROM students
            WHERE email IS NOT NULL
            ORDER BY first_name, last_name, created_at, id
            """
        )

        email_groups = {}
        updates = []

        for row in rows:
            email = row["email"]
            if email.endswith("@student.fairview-school.ng"):
                base_email = email.replace("@student.fairview-school.ng", "@fairviewschoolng.com")
            else:
                base_email = email

            if base_email not in email_groups:
                email_groups[base_email] = []
            email_groups[base_email].append({
                "id": row["id"], "name": f"{row['first_name']} {row['last_name']}",
                "old_email": email, "base_email": base_email
            })

        for base_email, students in email_groups.items():
            students[0]["final_email"] = base_email
            updates.append(students[0])
            for idx, student in enumerate(students[1:], start=2):
                parts = base_email.split("@")
                student["final_email"] = f"{parts[0]}{idx}@{parts[1]}"
                updates.append(student)

        print(f"Applying {len(updates)} email updates in single atomic transaction...")

        async with conn.transaction():
            for i, update in enumerate(updates, 1):
                await conn.execute(
                    "UPDATE students SET email = $1 WHERE id = $2",
                    update["final_email"], update["id"]
                )
                if i % 50 == 0 or i == len(updates):
                    print(f"  {i}/{len(updates)}...")

        print(f"[OK] {len(updates)} student emails updated")
        return 0

    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
