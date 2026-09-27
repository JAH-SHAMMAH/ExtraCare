"""Test helpers: the two preconditions for saving a mark.

Saving a mark now requires BOTH:

  * the pupil ENROLLED in the subject      -> `enrol` / `enrol_all`
  * the actor ASSIGNED to teach it         -> `assign_teaching`

Entering a mark is a teaching act, so there is no administrative bypass: a
superuser fixture with no teaching assignment is refused like anyone else. Tests
that drive mark entry therefore have to say who teaches the subject.

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


async def assign_teaching(db, org, teacher, class_obj, subject, day: int = 0):
    """Make `teacher` the teacher of (class, subject), via the Timetable.

    The Timetable is the primary source `_teacher_assignments` reads, and how all
    120 live (class, subject) pairs at Fairview are covered. `day_of_week`,
    `start_time` and `end_time` are NOT NULL, so a bare (class, subject, teacher)
    triple will not insert — hence this helper rather than an inline row.

    NOTE the fallback in `_teacher_assignments`: a teacher with ANY Timetable row
    is scoped to their Timetable pairs ONLY. Giving a teacher one assignment
    therefore NARROWS them to it, where before they may have matched every class
    through Subject.teacher_id.
    """
    import uuid as _uuid

    from app.models.modules.school import Timetable

    db.add(Timetable(
        id=str(_uuid.uuid4()),
        class_id=getattr(class_obj, "id", class_obj),
        subject_id=getattr(subject, "id", subject),
        teacher_id=getattr(teacher, "id", teacher),
        day_of_week=day, start_time="08:00", end_time="09:00",
        org_id=org.id if hasattr(org, "id") else org,
    ))
    await db.commit()


async def allow_marks(db, org, teacher, class_obj, subject, pupils, academic_year="2025/2026"):
    """Both preconditions at once: assign the teacher, enrol the pupils."""
    await assign_teaching(db, org, teacher, class_obj, subject)
    await enrol(db, org, pupils, subject, academic_year)


async def teach_everything(db, org, user):
    """Make `user` the subject teacher for every subject that has none.

    Uses `Subject.teacher_id` rather than Timetable rows on purpose: with no
    Timetable rows for this user, `_teacher_assignments` falls back to
    Subject.teacher_id and yields (every class x their subjects) — which is
    exactly the reach the removed admin bypass used to give. One field per
    subject, and it leaves any subject that already names a teacher alone, so a
    test that deliberately scopes somebody out keeps working.

    For tests whose subject is the report PIPELINE rather than who may author a
    mark. A test about the teaching gate itself should use `assign_teaching` with
    an explicit pair instead.
    """
    from sqlalchemy import select

    from app.models.modules.school import Subject

    subjects = (await db.execute(select(Subject).where(
        Subject.org_id == org.id, Subject.teacher_id.is_(None)))).scalars().all()
    for s in subjects:
        s.teacher_id = getattr(user, "id", user)
    await db.commit()
