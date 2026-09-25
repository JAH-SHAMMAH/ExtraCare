"""Grade Analysis can be scoped to one sub-term.

The query groups by AssessmentGroup, so a term holding both a Half-Term and a
Full-Term assessment in the same group summed them into ONE row — the teacher saw
a single total with no way to tell which sitting it came from. Term was already
filterable; sub-term was not, for no better reason than it had not been added.

Optional, like the term filter: omitting it returns the whole term, which is what
the endpoint did before. That is asserted, because the page ships with the filter
defaulted and a regression there would silently halve every total.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, AssessmentGroup, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject, Timetable
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.academics import list_grade_analysis


async def _teacher(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="teacher", slug=f"t-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["teacher"]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4().hex[:6]}@example.com",
             full_name="Teacher", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _fixture(db, org, teacher):
    """One term, two sub-terms, the SAME assessment group in both — the collision
    that made a sub-term filter necessary."""
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1", org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
    group = AssessmentGroup(id=str(uuid.uuid4()), name="Exams", position=0, org_id=org.id)
    db.add_all([cls, subj, term, half, full, group])
    await db.commit()

    stu = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="Musa",
                  last_name="Yusuf", class_id=cls.id, org_id=org.id)
    a_half = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=100, term_id=term.id,
                        sub_term_id=half.id, group_id=group.id, org_id=org.id)
    a_full = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=100, term_id=term.id,
                        sub_term_id=full.id, group_id=group.id, org_id=org.id)
    db.add_all([stu, a_half, a_full])
    await db.commit()

    db.add_all([
        StudentAssessmentScore(id=str(uuid.uuid4()), student_id=stu.id, subject_id=subj.id,
                               assessment_id=a_half.id, score=40, org_id=org.id),
        StudentAssessmentScore(id=str(uuid.uuid4()), student_id=stu.id, subject_id=subj.id,
                               assessment_id=a_full.id, score=70, org_id=org.id),
        Timetable(id=str(uuid.uuid4()), class_id=cls.id, subject_id=subj.id,
                  teacher_id=teacher.id, day_of_week=0, start_time="08:00",
                  end_time="09:00", org_id=org.id),
    ])
    await db.commit()
    return cls, subj, term, half, full


async def _analyse(db, teacher, **kw):
    return await list_grade_analysis(
        class_id=kw.get("class_id"), subject_id=kw.get("subject_id"),
        term_id=kw.get("term_id"), sub_term_id=kw.get("sub_term_id"),
        page=1, page_size=50, db=db, current_user=teacher,
    )


@pytest.mark.asyncio
async def test_without_a_sub_term_the_whole_term_is_returned(db, org):
    """Backward compatibility. Both sittings land in one group row, totalling 110
    of 200 — exactly what the endpoint did before the filter existed."""
    teacher = await _teacher(db, org)
    await _fixture(db, org, teacher)

    out = await _analyse(db, teacher)

    assert out["total"] == 1
    row = out["items"][0]
    assert float(row["total_score"]) == 110.0
    assert row["assessment_count"] == 2


@pytest.mark.asyncio
async def test_a_sub_term_narrows_to_that_sitting(db, org):
    teacher = await _teacher(db, org)
    _, _, _, half, full = await _fixture(db, org, teacher)

    h = await _analyse(db, teacher, sub_term_id=half.id)
    assert h["total"] == 1
    assert float(h["items"][0]["total_score"]) == 40.0
    assert h["items"][0]["assessment_count"] == 1

    f = await _analyse(db, teacher, sub_term_id=full.id)
    assert float(f["items"][0]["total_score"]) == 70.0


@pytest.mark.asyncio
async def test_an_unknown_sub_term_returns_nothing_rather_than_everything(db, org):
    """Failing open would silently undo the filter — the teacher would believe
    they had scoped the figures when they had not."""
    teacher = await _teacher(db, org)
    await _fixture(db, org, teacher)

    out = await _analyse(db, teacher, sub_term_id=str(uuid.uuid4()))
    assert out["total"] == 0 and out["items"] == []


@pytest.mark.asyncio
async def test_sub_term_composes_with_the_other_filters(db, org):
    """The filters narrow together; sub-term must not bypass the class/subject
    scoping that keeps a teacher to their own timetable."""
    teacher = await _teacher(db, org)
    cls, subj, term, half, _ = await _fixture(db, org, teacher)

    out = await _analyse(db, teacher, class_id=cls.id, subject_id=subj.id,
                         term_id=term.id, sub_term_id=half.id)
    assert out["total"] == 1 and float(out["items"][0]["total_score"]) == 40.0

    # A class this teacher does not teach still yields nothing, sub-term or not.
    out = await _analyse(db, teacher, class_id=str(uuid.uuid4()), sub_term_id=half.id)
    assert out["total"] == 0
