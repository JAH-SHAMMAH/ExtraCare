"""Read-only: can a PARENT actually open their child's report card?

The report card gates parents on the workflow row, resolved BY TERM ID:

    ReportApproval.class_id == cls.id AND ReportApproval.term_id == term_record.id
    ... and stage must be 'published', else 403.

It used to match on the term NAME, and that is how this broke: approvals said
'Term 1' while the only selectable terms were Autumn/Spring/Summer, so the
lookup matched nothing and every parent got "This report has not been published
yet" for every term — a silent second symptom of the term drift that broke the
CBT sync. Migration 131 replaced the name with a foreign key, so a name can no
longer drift out from under the gate. This script still earns its keep: it
proves the gate OPENS, which a schema change on its own does not.

Reasoning about the data is not proof the gate opens. This drives the endpoint
as the real parent user, which is the only thing that actually answers it.

    python scripts/verify_parent_report_card.py <DSN>
    python scripts/verify_parent_report_card.py <DSN> --student "Musa Yusuf"

Without --student it samples whatever parent/child pairs the data offers, which
answers "does the gate open at all". With --student it drives one named child,
which is what you want when somebody reports that ONE card will not open.
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def _wanted_student(argv) -> str | None:
    """The value of --student, whether written as `--student X` or `--student=X`."""
    for i, a in enumerate(argv):
        if a == "--student" and i + 1 < len(argv):
            return argv[i + 1].strip()
        if a.startswith("--student="):
            return a.split("=", 1)[1].strip()
    return None


def _resolve(argv) -> str:
    skip = False
    for a in argv[1:]:
        if skip:                      # this one is --student's value, not the DSN
            skip = False
            continue
        if a == "--student":
            skip = True
            continue
        if not a.startswith("--"):
            return a.split("?")[0]
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env.split("?")[0]
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def main() -> int:
    url = _resolve(sys.argv)
    engine = create_async_engine(url, echo=False, connect_args={"ssl": "require"})
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from app.models.modules.platform import AcademicSubTerm, AcademicTerm
    from app.models.modules.school import ParentGuardian, SchoolClass, Student
    from app.models.user import User
    from app.routers.modules.platform import report_card

    async with Session() as db:
        term = (await db.execute(
            select(AcademicTerm).where(AcademicTerm.name == "Autumn")
        )).scalars().first()
        sub = (await db.execute(
            select(AcademicSubTerm).where(AcademicSubTerm.name.in_(["Full-Term", "Full Term"]))
        )).scalars().first()
        if not term or not sub:
            sys.exit("No Autumn term / Full-Term sub-term found.")
        print(f"term    : {term.name} ({term.id})")
        print(f"sub-term: {sub.name}\n")

        # A real parent with a real linked child, picked from the data rather
        # than constructed — a synthetic user would not prove the live gate.
        wanted = _wanted_student(sys.argv)
        if wanted:
            parts = wanted.split()
            q = select(Student)
            for p in parts:
                q = q.where(
                    (Student.first_name.ilike(f"%{p}%")) | (Student.last_name.ilike(f"%{p}%"))
                )
            kids = (await db.execute(q.limit(10))).scalars().all()
            if not kids:
                sys.exit(f"No student matches {wanted!r}.")
            if len(kids) > 1:
                names = ", ".join(f"{k.first_name} {k.last_name}" for k in kids)
                sys.exit(f"{wanted!r} is ambiguous — matched: {names}")
            kid = kids[0]
            print(f"student : {kid.first_name} {kid.last_name} ({kid.id})")
            link = (await db.execute(
                select(ParentGuardian).where(ParentGuardian.student_id == kid.id)
            )).scalars().all()
            if not link:
                sys.exit(f"{kid.first_name} {kid.last_name} has no linked parent/guardian, "
                         f"so there is no parent whose access could be tested.")
            print(f"parents : {len(link)} linked")
            print()
        else:
            link = (await db.execute(select(ParentGuardian).limit(50))).scalars().all()
        checked = 0
        for pg in link:
            parent = (await db.execute(
                select(User).where(User.id == pg.user_id)
            )).scalars().first()
            student = (await db.execute(
                select(Student).where(Student.id == pg.student_id)
            )).scalars().first()
            if not parent or not student or not student.class_id:
                continue
            cls = (await db.execute(
                select(SchoolClass).where(SchoolClass.id == student.class_id)
            )).scalars().first()

            # Confirm this really is the restricted path: a parent must NOT hold
            # school:students:read, or the gate is skipped and proves nothing.
            broad = parent.has_permission("school:students:read")
            print(f"parent  : {parent.email}")
            print(f"child   : {student.first_name} {student.last_name}  ({cls.name if cls else '?'})")
            print(f"  holds school:students:read : {broad}"
                  f"{'   <-- staff-ish, gate skipped, not a real test' if broad else '   (so the parent gate applies)'}")
            if broad:
                print()
                continue

            try:
                card = await report_card(
                    student_id=student.id, term_id=term.id, sub_term_id=sub.id,
                    db=db, current_user=parent,
                )
            except Exception as e:
                detail = getattr(e, "detail", str(e))
                status = getattr(e, "status_code", "?")
                print(f"  RESULT : BLOCKED ({status}) - {detail}\n")
                checked += 1
                continue

            subjects = getattr(card, "subjects", None) or []
            print(f"  RESULT : OPENED")
            print(f"           subjects on the card : {len(subjects)}")
            for s in subjects[:3]:
                print(f"             - {getattr(s, 'subject_name', '?')}: "
                      f"total={getattr(s, 'total', None)}")
            print()
            checked += 1
            if not wanted and checked >= 3:
                break

        if not checked:
            print("No parent/child pair could be tested.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
