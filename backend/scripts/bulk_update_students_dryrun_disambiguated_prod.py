#!/usr/bin/env python3
import sys
import asyncio

async def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/bulk_update_students_dryrun_disambiguated_prod.py '<postgresql_url>'")
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
        all_changes = []

        for row in rows:
            email = row["email"]
            name = f"{row['first_name']} {row['last_name']}"

            if email.endswith("@student.fairview-school.ng"):
                base_email = email.replace("@student.fairview-school.ng", "@fairviewschoolng.com")
            else:
                base_email = email

            if base_email not in email_groups:
                email_groups[base_email] = []

            email_groups[base_email].append({
                "id": row["id"], "name": name, "old_email": email,
                "base_email": base_email, "created_at": row["created_at"]
            })

        for base_email, students in email_groups.items():
            students[0]["final_email"] = base_email
            all_changes.append(students[0])
            for idx, student in enumerate(students[1:], start=2):
                parts = base_email.split("@")
                student["final_email"] = f"{parts[0]}{idx}@{parts[1]}"
                all_changes.append(student)

        all_changes.sort(key=lambda x: (x["name"], x["id"]))

        changes = [c for c in all_changes if c["old_email"] != c["final_email"]]
        unchanged = [c for c in all_changes if c["old_email"] == c["final_email"]]

        print("\n" + "="*140)
        print("EMAIL UPDATE DRY-RUN (DISAMBIGUATED)")
        print("="*140)

        print(f"\nCHANGES TO BE MADE ({len(changes)} records):")
        print("-" * 140)
        for i, change in enumerate(changes, 1):
            print(f"{i:<4} {change['name']:<30} {change['old_email']:<50} {change['final_email']:<50}")

        print(f"\nUNCHANGED ({len(unchanged)} records):")
        for i, u in enumerate(unchanged, 1):
            print(f"  {i:3d}. {u['name']:<30} | {u['old_email']}")

        print("\n" + "="*140)
        print("SUMMARY")
        print("="*140)
        print(f"Students to update: {len(changes)}")
        print(f"Unchanged: {len(unchanged)}")
        print(f"Total: {len(changes) + len(unchanged)}")

        disambiguated = len([c for c in changes if c["final_email"] != c["base_email"]])
        print(f"\nDisambiguations applied: {disambiguated}")

        return 0

    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
