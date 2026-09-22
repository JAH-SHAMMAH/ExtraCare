"""Give each class teacher the TeacherSection row their class already implies.

`report_broadsheet` gates Reports View twice: you must be the class's teacher AND
have a TeacherSection row for that class's section. `teacher_sections` is empty
while all 30 classes carry a section_id, so the second gate refuses EVERY
teacher — including the actual class teacher. Only admins get through, via
`_report_admin`, which is why it went unnoticed.

The gate is correct; the table behind it was never populated. This fills it in
from data that already exists rather than loosening the gate.

DERIVATION, and why it needs no judgement: a class teacher's section is the
section of the classes they teach. Fairview's 15 class teachers each hold 2
classes, all within ONE section, so every row is unambiguous. A teacher whose
classes span several sections is REFUSED, not guessed at —
uq_teacher_section_org_teacher allows one section per teacher, so picking one
would be inventing an answer.

Admins can already do this per teacher in the UI (Teachers → Assign to School,
POST /school/teachers/{id}/assign-section). This is the one-time catch-up, not a
replacement for that flow.

DRY RUN BY DEFAULT. Nothing is written without --write.

    python -m scripts.backfill_teacher_sections "<DSN>"
    python -m scripts.backfill_teacher_sections "<DSN>" --write
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import SchoolClass, TeacherSection
from app.models.user import User


def _dsn() -> str:
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            return a.split("?")[0]
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env.split("?")[0]
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def main() -> int:
    write = "--write" in sys.argv
    engine = create_async_engine(_dsn(), echo=False, connect_args={"ssl": "require"})
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        from app.models.modules.platform import SchoolSection

        classes = (await db.execute(
            select(SchoolClass).where(
                SchoolClass.teacher_id.is_not(None),
                SchoolClass.section_id.is_not(None),
            )
        )).scalars().all()
        sections = {s.id: s.name for s in (await db.execute(select(SchoolSection))).scalars().all()}
        names = {u.id: (u.full_name or u.email) for u in (await db.execute(select(User))).scalars().all()}

        # teacher -> {section_id: [class names]}
        owned: dict[str, dict[str, list[str]]] = {}
        for c in classes:
            owned.setdefault(c.teacher_id, {}).setdefault(c.section_id, []).append(c.name)

        existing = {
            (t.org_id, t.teacher_id): t
            for t in (await db.execute(select(TeacherSection))).scalars().all()
        }
        org_of = {c.teacher_id: c.org_id for c in classes}

        print(f"{'WRITE' if write else 'DRY RUN'} — class teachers found: {len(owned)}")
        print(f"existing teacher_sections rows: {len(existing)}\n")

        to_write, skipped, ambiguous = [], [], []
        for teacher_id, by_section in sorted(owned.items(), key=lambda kv: names.get(kv[0], "")):
            who = names.get(teacher_id, teacher_id)
            org_id = org_of[teacher_id]
            if len(by_section) > 1:
                ambiguous.append((who, by_section))
                continue
            section_id = next(iter(by_section))
            classes_held = ", ".join(sorted(by_section[section_id]))
            if (org_id, teacher_id) in existing:
                cur = existing[(org_id, teacher_id)]
                same = cur.section_id == section_id
                skipped.append((who, sections.get(cur.section_id), same))
                continue
            to_write.append((teacher_id, org_id, section_id))
            print(f"  + {who:<20} -> {sections.get(section_id, '?'):<10}  (from {classes_held})")

        if skipped:
            print(f"\n  {len(skipped)} teacher(s) already have a row:")
            for who, sec, same in skipped:
                note = "matches" if same else "DIFFERENT — left alone, not overwritten"
                print(f"    = {who:<20} -> {sec} ({note})")

        if ambiguous:
            # Never guessed: one section per teacher is a unique constraint, so
            # choosing one here would be inventing an answer an admin should give.
            print(f"\n  !! {len(ambiguous)} teacher(s) span several sections — REFUSED, assign "
                  f"these by hand in Teachers -> Assign to School:")
            for who, by_section in ambiguous:
                print(f"    ? {who}: " + "; ".join(
                    f"{sections.get(sid, '?')} ({', '.join(sorted(cl))})" for sid, cl in by_section.items()))

        print(f"\nrows to insert: {len(to_write)}")

        if write and to_write:
            for teacher_id, org_id, section_id in to_write:
                db.add(TeacherSection(id=str(uuid.uuid4()), teacher_id=teacher_id,
                                      section_id=section_id, org_id=org_id))
            await db.commit()
            print(f"[OK] inserted {len(to_write)} row(s).")
        elif not write:
            print("DRY RUN — nothing written. Re-run with --write to apply.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
