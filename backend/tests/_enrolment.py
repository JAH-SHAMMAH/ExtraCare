"""Test helper: make a (pupil, subject) pair markable.

Subject enrolment gates mark entry (migration 128, services/subject_enrollment).
Any test that saves a mark therefore has to enrol first — the same thing a real
school does before a teacher can record anything.

Deliberately NOT a conftest autouse fixture. Enrolment being a precondition is
the behaviour under test in several places, and a fixture that silently enrolled
everybody would hide exactly the bug the gate exists to catch. Tests call this
explicitly, so it is visible that enrolment happened.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


async def enrol(db, org, students, subjects, academic_year: str = "2025/2026"):
    """Enrol every (pupil, subject) combination so their marks can be saved.

    `students` / `subjects` each take a single object or an iterable. Idempotent,
    so calling it twice for the same pair is harmless.
    """
    from sqlalchemy import select

    from app.models.modules.academics import StudentSubjectEnrollment

    stus = list(students) if isinstance(students, (list, tuple, set)) else [students]
    subs = list(subjects) if isinstance(subjects, (list, tuple, set)) else [subjects]

    have = {
        (r.student_id, r.subject_id)
        for r in (await db.execute(
            select(StudentSubjectEnrollment).where(
                StudentSubjectEnrollment.org_id == org.id,
                StudentSubjectEnrollment.academic_year == academic_year,
            )
        )).scalars().all()
    }

    now = datetime.now(timezone.utc)
    for st in stus:
        for sb in subs:
            sid = getattr(st, "id", st)
            bid = getattr(sb, "id", sb)
            if (sid, bid) in have:
                continue
            db.add(StudentSubjectEnrollment(
                id=str(uuid.uuid4()), org_id=org.id, student_id=sid, subject_id=bid,
                academic_year=academic_year, enrolled_at=now, source="manual"))
    await db.commit()


async def enrol_all(db, org, academic_year: str = "2025/2026"):
    """Enrol every pupil in every subject in the org.

    For pipeline tests whose subject is the report engine rather than the
    enrolment gate — Report Entry -> Broadsheet -> Card -> Insight -> Upload.
    They predate the gate and mark whole classes across every subject, so
    enumerating pairs in each would be noise that obscures what they assert.

    Tests that are ABOUT the gate use `enrol` above with explicit pairs, so the
    thing under test is never handed to them for free.
    """
    from sqlalchemy import select

    from app.models.modules.school import Student, Subject

    students = (await db.execute(select(Student).where(
        Student.org_id == org.id, Student.is_deleted == False))).scalars().all()  # noqa: E712
    subjects = (await db.execute(select(Subject).where(Subject.org_id == org.id))).scalars().all()
    await enrol(db, org, students, subjects, academic_year)
