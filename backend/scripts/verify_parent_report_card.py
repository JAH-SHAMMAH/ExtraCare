"""Read-only: can a PARENT actually open their child's report card?

The new report card gates parents on the workflow row, resolved BY TERM NAME:

    ReportApproval.class_id == cls.id AND ReportApproval.term == term_record.name
    ... and stage must be 'published', else 403.

While approvals said 'Term 1' and the only selectable terms were
Autumn/Spring/Summer, that lookup matched nothing and every parent got
"This report has not been published yet" for every term — a silent second
symptom of the same term drift that broke the CBT sync.

Reasoning about the data is not proof the gate opens. This drives the endpoint
as the real parent user, which is the only thing that actually answers it.

    python scripts/verify_parent_report_card.py <DSN>
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def _resolve(argv) -> str:
    for a in argv[1:]:
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
            if checked >= 3:
                break

        if not checked:
            print("No parent/child pair could be tested.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
