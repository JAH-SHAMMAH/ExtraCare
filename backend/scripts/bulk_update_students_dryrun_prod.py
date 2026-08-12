#!/usr/bin/env python3
import sys
import asyncio

async def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/bulk_update_students_dryrun_prod.py '<postgresql_url>'")
        return 2

    database_url = sys.argv[1].strip().split("?")[0]

    import asyncpg

    conn = await asyncpg.connect(database_url, ssl="require")

    try:
        rows = await conn.fetch(
            """
            SELECT id, first_name, last_name, email
            FROM students
            WHERE email IS NOT NULL
            ORDER BY first_name, last_name
            """
        )

        changes = []
        unchanged = []

        for row in rows:
            email = row["email"]
            name = f"{row['first_name']} {row['last_name']}"

            if email.endswith("@student.fairview-school.ng"):
                new_email = email.replace("@student.fairview-school.ng", "@fairviewschoolng.com")
                changes.append({"id": row["id"], "name": name, "old": email, "new": new_email})
            else:
                unchanged.append({"name": name, "email": email})

        print("\n" + "="*120)
        print("EMAIL UPDATE DRY-RUN")
        print("="*120)

        print(f"\nCHANGES TO BE MADE ({len(changes)} records):")
        print("-" * 120)
        for i, change in enumerate(changes, 1):
            print(f"  {i:3d}. {change['name']:<30} | {change['old']:<40} -> {change['new']}")

        print(f"\n\nUNCHANGED ({len(unchanged)} records):")
        print("-" * 120)
        for i, u in enumerate(unchanged, 1):
            print(f"  {i:3d}. {u['name']:<30} | {u['email']}")

        print("\n" + "="*120)
        print("SUMMARY")
        print("="*120)
        print(f"Students to update: {len(changes)}")
        print(f"Unchanged: {len(unchanged)}")
        print(f"Total: {len(changes) + len(unchanged)}")

        return 0

    except Exception as e:
        print(f"[ERROR] Dry-run failed: {e}")
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
