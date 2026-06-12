"""
One-shot migrations for additive columns SQLAlchemy's `create_all` won't add.

This script grew from a Phase 6.3 helper into a small running list of
"add-this-column-if-missing" patches. Every step is idempotent — safe to
re-run any time.

Currently covers:
  - Phase 6.3: students.user_id (multi-role link)
  - Phase 6.6 polish: sms_messages.provider_status_raw (webhook-ready)

Usage:
    cd backend
    venv/Scripts/python -m scripts.migrate_add_user_links
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from app.database import AsyncSessionLocal, init_db


async def _column_exists(db, table: str, column: str) -> bool:
    rows = (await db.execute(text(f"PRAGMA table_info({table})"))).all()
    return any(r[1] == column for r in rows)


async def _table_exists(db, table: str) -> bool:
    row = (await db.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": table},
    )).first()
    return row is not None


async def main() -> int:
    # Make sure new tables (parent_guardians) exist via create_all first.
    await init_db()

    async with AsyncSessionLocal() as db:
        did_work = False

        # students.user_id — nullable FK linking a student row to its login.
        if not await _column_exists(db, "students", "user_id"):
            await db.execute(text("ALTER TABLE students ADD COLUMN user_id VARCHAR(36)"))
            # SQLite lets us add an index after the column exists.
            await db.execute(text("CREATE INDEX IF NOT EXISTS ix_students_user_id ON students(user_id)"))
            print("added column: students.user_id (+ index)")
            did_work = True
        else:
            print("skip: students.user_id already exists")

        # Defensive — should already be there via init_db(), but confirm.
        if not await _table_exists(db, "parent_guardians"):
            print("warn: parent_guardians table missing after init_db()")
        else:
            print("ok: parent_guardians table present")

        # Phase 6.6 polish: webhook-ready provider status payload.
        if await _table_exists(db, "sms_messages"):
            if not await _column_exists(db, "sms_messages", "provider_status_raw"):
                await db.execute(text("ALTER TABLE sms_messages ADD COLUMN provider_status_raw JSON"))
                print("added column: sms_messages.provider_status_raw")
                did_work = True
            else:
                print("skip: sms_messages.provider_status_raw already exists")

        if did_work:
            await db.commit()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
