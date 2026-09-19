"""Read-only: does every class have a teacher who could submit its report?

POST /academics/report-workflow/submit is limited to the class's PC teacher,
resolved by `_pc_teacher_id` — a ClassPcTeacher row if one exists, otherwise
SchoolClass.teacher_id. A class with neither has nobody who can hand its report
in, and the feature is silently unavailable for it.

The endpoint says so rather than blaming the teacher, but a class that cannot be
submitted at all is a setup gap worth knowing about BEFORE rollout rather than
from a confused teacher.

SchoolClass carries no SoftDeleteMixin - unlike Student, school_classes has
no soft-delete column - so every row counts.

Read-only by construction: SELECTs only, no transaction, no writes. Safe to run
against production.

    python scripts/check_class_teachers.py "postgresql://user:pass@host/db"

or set DATABASE_URL. A +asyncpg:// or postgresql+asyncpg:// URL is accepted and
normalised — asyncpg wants the bare scheme.
"""
from __future__ import annotations

import asyncio
import os
import sys


def _normalise(url: str) -> str:
    """SQLAlchemy-style URLs carry a driver the asyncpg client rejects."""
    url = url.strip()
    for prefix, repl in (
        ("postgresql+asyncpg://", "postgresql://"),
        ("postgres+asyncpg://", "postgresql://"),
        ("postgres://", "postgresql://"),
    ):
        if url.startswith(prefix):
            url = repl + url[len(prefix):]
            break
    # Render's copy-paste form; libpq spells it sslmode=
    return url.replace("?ssl=require", "?sslmode=require")


async def main(url: str) -> int:
    import asyncpg

    conn = await asyncpg.connect(_normalise(url))
    try:
        total, with_teacher = await conn.fetchrow(
            """
            SELECT COUNT(*)            AS total,
                   COUNT(teacher_id)   AS with_teacher
            FROM school_classes
            """
        )
        pc_rows = await conn.fetchval("SELECT COUNT(*) FROM class_pc_teachers")

        # The real question: classes reachable by NEITHER route.
        orphans = await conn.fetch(
            """
            SELECT c.name
            FROM school_classes c
            LEFT JOIN class_pc_teachers p ON p.class_id = c.id
              WHERE c.teacher_id IS NULL
              AND p.teacher_id IS NULL
            ORDER BY c.name
            """
        )

        print(f"classes                    : {total}")
        print(f"  with SchoolClass.teacher : {with_teacher}")
        print(f"  ClassPcTeacher rows      : {pc_rows}")
        print(f"  NO submitter either way  : {len(orphans)}")
        if orphans:
            print("\nThese classes have nobody who can submit their report:")
            for r in orphans:
                print(f"  - {r['name']}")
            print(
                "\nAssign a class teacher (or a ClassPcTeacher row) for each, or only "
                "an administrator will be able to submit them."
            )
        else:
            print("\n[OK] every class has someone who can submit its report.")
        return 1 if orphans else 0
    finally:
        await conn.close()


if __name__ == "__main__":
    dsn = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATABASE_URL", "")
    if not dsn:
        sys.exit("Pass a connection string, or set DATABASE_URL.")
    raise SystemExit(asyncio.run(main(dsn)))
