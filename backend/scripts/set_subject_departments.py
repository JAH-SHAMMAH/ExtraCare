#!/usr/bin/env python
"""Set each subject's department. Dry run unless --write is passed.

The mapping is the school's, given by name. Two of the names it uses are
ABBREVIATIONS of what the database holds — "CRS" for Christian Religious Studies
and "IT" for Information Technology — so the resolution is explicit and printed,
rather than a fuzzy match that might silently bind the wrong subject.

`subjects.department` already exists and is NULL for all ten. Nothing reads it
yet; Departmental Analysis will be its first consumer, which is why it was
blocked until now.

    python scripts/set_subject_departments.py <DSN>
    python scripts/set_subject_departments.py <DSN> --write
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# department -> the subject names it contains, as the school gave them.
DEPARTMENTS: dict[str, list[str]] = {
    "Mathematics": ["Mathematics"],
    "Languages": ["English Language"],
    "Sciences": ["Physics", "Chemistry", "Biology"],
    "Social Sciences": ["Government", "Economics", "Geography"],
    "Religious Studies": ["CRS"],
    "ICT": ["IT"],
}

# Where the school's shorthand and the stored name differ. Listed rather than
# inferred: a prefix or substring match would happily bind "IT" to any subject
# containing those letters.
ALIASES: dict[str, str] = {
    "CRS": "Christian Religious Studies",
    "IT": "Information Technology",
}


def _resolve(argv) -> str:
    for a in argv[1:]:
        if not a.startswith("--"):
            return a.split("?")[0]
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env.split("?")[0]
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def main() -> int:
    write = "--write" in sys.argv
    engine = create_async_engine(_resolve(sys.argv), echo=False,
                                 connect_args={"ssl": "require"})
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    from app.models.modules.school import Subject

    async with Session() as db:
        subjects = (await db.execute(select(Subject).where(
            Subject.org_id.isnot(None)))).scalars().all()
        by_name = {s.name: s for s in subjects}

        print(f"subjects in the database: {len(subjects)}")
        planned: list[tuple] = []
        unresolved: list[str] = []
        for dept, names in DEPARTMENTS.items():
            for given in names:
                stored = ALIASES.get(given, given)
                subj = by_name.get(stored)
                if subj is None:
                    unresolved.append(f"{given!r} -> {stored!r}")
                    continue
                note = f"  (given as {given!r})" if stored != given else ""
                planned.append((subj, dept, stored, note))

        print("\n== PLAN ==")
        for subj, dept, stored, note in planned:
            was = subj.department or "(null)"
            change = "no change" if subj.department == dept else f"{was} -> {dept}"
            print(f"   {stored:32} {dept:18} {change}{note}")

        if unresolved:
            print("\n   UNRESOLVED (refusing to guess):")
            for u in unresolved:
                print(f"      {u}")

        covered = {s.id for s, _, _, _ in planned}
        missed = [s for s in subjects if s.id not in covered]
        if missed:
            print(f"\n   subjects NOT in the mapping ({len(missed)}): "
                  f"{', '.join(sorted(s.name for s in missed))}")
            print("   these keep whatever department they have; the mapping is not a")
            print("   statement that every other subject has none.")

        changing = [p for p in planned if p[0].department != p[1]]
        print(f"\n   rows to update: {len(changing)}   (of {len(planned)} mapped)")

        if unresolved:
            print("\nRefusing: resolve the names above first.")
            return 1
        if not write:
            print("\n(dry run — nothing written. Pass --write.)")
            return 0

        for subj, dept, _stored, _note in changing:
            subj.department = dept
        await db.commit()
        print(f"\nupdated {len(changing)} subject(s)")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
