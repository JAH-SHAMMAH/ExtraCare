#!/usr/bin/env python3
import sys
import asyncio
import csv
from datetime import datetime

async def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/bulk_update_students_backup_prod.py '<postgresql_url>'")
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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"student_email_backup_{timestamp}.csv"

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["student_id", "first_name", "last_name", "current_email", "backup_timestamp"])
            for row in rows:
                writer.writerow([row["id"], row["first_name"], row["last_name"], row["email"], timestamp])

        print("BACKUP COMPLETE")
        print(f"File: {filename}")
        print(f"Records: {len(rows)} students")
        return 0

    except Exception as e:
        print(f"[ERROR] Backup failed: {e}")
        return 1
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
