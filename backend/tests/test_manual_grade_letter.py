"""A mark entered by hand gets a letter, like every other way of writing one.

Three paths write a Grade row. The CBT gradebook feed and the exam-results path
have always stamped `grade_letter`; POST /school/grades never did. So a mark a
teacher typed reached the parent report card with a blank Grade column, sitting
beside a CBT-fed mark that showed one — the same table, the same term, two
different-looking rows for no reason the reader could see.

Found while checking a live parent card: every one of Musa Yusuf's ten subjects
showed a score and no letter. (Those particular rows are a separate matter — a
bootstrap script wrote them outside the real feed — but this path was genuinely
missing the assignment, and would have kept producing letterless rows.)

NOTE for whoever picks up the grading-scale work: `grade_letter` currently reads
a hardcoded five-band constant, while Fairview has nine bands configured in
`grading_bands`. These tests assert only that a letter IS derived from the shared
helper, never which letter a given percentage maps to, so correcting the helper
to read the configured bands will not break them.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.modules.school import Grade, SchoolClass, Student, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.school import submit_grades
from app.services.grading import grade_letter


async def _teacher(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="teacher", slug=f"t-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["teacher"]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"t-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Teacher", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _fixture(db, org):
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    db.add_all([cls, subj])
    await db.commit()
    stu = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="Musa", last_name="Yusuf",
                  class_id=cls.id, org_id=org.id)
    db.add(stu)
    await db.commit()
    return stu, subj


async def _submit(db, user, stu, subj, score, max_score=100):
    return await submit_grades(
        [{"student_id": stu.id, "subject_id": subj.id, "score": score,
          "max_score": max_score, "term": "Autumn"}],
        request=None, db=db, current_user=user,
    )


@pytest.mark.asyncio
async def test_a_hand_entered_mark_gets_a_letter(db, org):
    teacher = await _teacher(db, org)
    stu, subj = await _fixture(db, org)

    await _submit(db, teacher, stu, subj, 72)

    g = (await db.execute(select(Grade))).scalars().one()
    assert g.score == 72
    assert g.grade_letter is not None, "the whole defect: a letterless hand-entered mark"


@pytest.mark.asyncio
async def test_the_letter_matches_the_shared_helper(db, org):
    """Derived from the same helper as the CBT feed, not a second copy of the
    thresholds — so correcting the scale in one place corrects every path."""
    teacher = await _teacher(db, org)
    stu, subj = await _fixture(db, org)

    await _submit(db, teacher, stu, subj, 64)

    g = (await db.execute(select(Grade))).scalars().one()
    assert g.grade_letter == grade_letter(64, 100)


@pytest.mark.asyncio
async def test_a_mark_out_of_something_other_than_100_is_scaled_not_taken_raw(db, org):
    """45/50 is 90%, not 45%. Passing max_score through matters: taking the raw
    number would letter a strong mark as a weak one."""
    teacher = await _teacher(db, org)
    stu, subj = await _fixture(db, org)

    await _submit(db, teacher, stu, subj, 45, max_score=50)

    g = (await db.execute(select(Grade))).scalars().one()
    assert g.grade_letter == grade_letter(45, 50)
    assert g.grade_letter != grade_letter(45, 100), "max_score was ignored"


@pytest.mark.asyncio
async def test_a_missing_score_yields_no_letter_rather_than_an_error(db, org):
    """The endpoint accepts a row with no mark yet. That must stay a None letter,
    not a crash and not a spurious F."""
    teacher = await _teacher(db, org)
    stu, subj = await _fixture(db, org)

    await _submit(db, teacher, stu, subj, None)

    g = (await db.execute(select(Grade))).scalars().one()
    assert g.score is None and g.grade_letter is None


@pytest.mark.asyncio
async def test_several_marks_in_one_call_each_get_their_own_letter(db, org):
    """The endpoint takes a list; a loop that computed the letter once outside it
    would stamp every row with the first mark's grade."""
    teacher = await _teacher(db, org)
    stu, subj = await _fixture(db, org)
    other = Subject(id=str(uuid.uuid4()), name="English", org_id=org.id)
    db.add(other)
    await db.commit()

    await submit_grades(
        [{"student_id": stu.id, "subject_id": subj.id, "score": 95, "max_score": 100, "term": "Autumn"},
         {"student_id": stu.id, "subject_id": other.id, "score": 41, "max_score": 100, "term": "Autumn"}],
        request=None, db=db, current_user=teacher,
    )

    rows = {g.subject_id: g.grade_letter for g in (await db.execute(select(Grade))).scalars().all()}
    assert rows[subj.id] == grade_letter(95, 100)
    assert rows[other.id] == grade_letter(41, 100)
    assert rows[subj.id] != rows[other.id], "one letter was reused for both marks"
