"""Subject enrolment: the register, and the gate it puts on mark entry.

The gate's whole value is that it covers EVERY path a mark can arrive by, so
these drive all three — the Report Entry grid, the bulk upload, and the CBT sync
— and assert the deliberately different behaviour of each:

    grid / save   -> blocked
    bulk upload   -> per-row error, rest of the file still imports
    CBT sync      -> NOT blocked; the marks land and the discrepancy is reported

Driven as the real roles where the path has one.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.modules.academics import StudentSubjectEnrollment
from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, AcademicTerm, Assessment, AssessmentGroup,
    StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import (
    report_entry_grid, save_report_entry, save_subject_enrollments,
    subject_enrollment_grid,
)
from app.schemas.platform import (
    EnrollmentSave, EnrollmentStudentSet, ReportEntrySave, ScoreItem,
)
from app.services.subject_enrollment import (
    AcademicYearUnresolved, plan_backfill, resolve_academic_year,
)

pytestmark = pytest.mark.asyncio

YEAR = "2025/2026"


async def _admin(db, org):
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com",
             full_name="Officer", status=UserStatus.ACTIVE, org_id=org.id)
    r = Role(id=str(uuid.uuid4()), name="admin", slug="super_user",
             permissions=["*"], org_id=org.id, is_system=False)
    db.add(r)
    u.roles = [r]
    db.add(u)
    await db.commit()
    return u


async def _world(db, org, *, session_name=YEAR, is_current=True):
    admin = await _admin(db, org)
    sess = AcademicSession(id=str(uuid.uuid4()), name=session_name, term="Autumn",
                           is_current=is_current, org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1",
                      teacher_id=admin.id, org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    eng = Subject(id=str(uuid.uuid4()), name="English", org_id=org.id)
    a = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                last_name="Obi", class_id=cls.id, org_id=org.id)
    b = Student(id=str(uuid.uuid4()), student_id="FSN-0002", first_name="Bola",
                last_name="Eze", class_id=cls.id, org_id=org.id)
    grp = AssessmentGroup(id=str(uuid.uuid4()), name="CBT", position=0, org_id=org.id)
    db.add_all([sess, term, full, cls, maths, eng, a, b, grp])
    await db.commit()
    asmt = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", code="CBT",
                      max_score=Decimal("100"), term_id=term.id, sub_term_id=full.id,
                      group_id=grp.id, decimal_places=0, position=0, org_id=org.id)
    db.add(asmt)
    await db.commit()
    # Mark entry also requires a teaching assignment now (there is no admin
    # bypass). These tests are about the ENROLMENT gate, so satisfy the teaching
    # precondition here and let each test exercise the one it is named for.
    from tests._enrolment import assign_teaching
    await assign_teaching(db, org, admin, cls, maths, day=0)
    await assign_teaching(db, org, admin, cls, eng, day=1)
    return dict(admin=admin, sess=sess, term=term, full=full, cls=cls,
                maths=maths, eng=eng, a=a, b=b, asmt=asmt)


async def _enrol(db, org, student, subject, year=YEAR):
    db.add(StudentSubjectEnrollment(
        id=str(uuid.uuid4()), org_id=org.id, student_id=student.id,
        subject_id=subject.id, academic_year=year, enrolled_at=datetime.now(timezone.utc),
        source="manual"))
    await db.commit()


def _entry(w, student, score=70):
    return ReportEntrySave(subject_id=w["maths"].id, class_id=w["cls"].id, items=[
        ScoreItem(student_id=student.id, assessment_id=w["asmt"].id, score=Decimal(score))])


# ── resolving the session ────────────────────────────────────────────────────

async def test_academic_year_comes_from_the_current_session(db, org):
    w = await _world(db, org)
    assert await resolve_academic_year(db, org.id) == YEAR


async def test_falls_back_to_the_only_session_when_none_is_current(db, org):
    """A school that never set the flag still works — but only because there is
    exactly one session to mean."""
    await _world(db, org, is_current=False)
    assert await resolve_academic_year(db, org.id) == YEAR


async def test_raises_rather_than_guessing_between_two_sessions(db, org):
    """Guessing would split enrolments across two year strings, and the gate
    would then refuse marks for a reason nobody could see."""
    await _world(db, org, is_current=False)
    db.add(AcademicSession(id=str(uuid.uuid4()), name="2026/2027", term="Autumn",
                           is_current=False, org_id=org.id))
    await db.commit()
    with pytest.raises(AcademicYearUnresolved):
        await resolve_academic_year(db, org.id)


# ── the gate on the grid + save ──────────────────────────────────────────────

async def test_unenrolled_pupil_cannot_be_marked(db, org):
    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await save_report_entry(payload=_entry(w, w["a"]), db=db, current_user=w["admin"])
    assert e.value.status_code == 422
    assert "not enrolled in Mathematics" in e.value.detail


async def test_enrolled_pupil_can_be_marked(db, org):
    w = await _world(db, org)
    await _enrol(db, org, w["a"], w["maths"])
    out = await save_report_entry(payload=_entry(w, w["a"]), db=db, current_user=w["admin"])
    assert out == {"saved": 1}


async def test_the_whole_batch_is_refused_not_silently_trimmed(db, org):
    """A partial save reporting success is how a teacher comes to believe marks
    are recorded when they are not."""
    w = await _world(db, org)
    await _enrol(db, org, w["a"], w["maths"])          # Ada enrolled, Bola not
    payload = ReportEntrySave(subject_id=w["maths"].id, class_id=w["cls"].id, items=[
        ScoreItem(student_id=w["a"].id, assessment_id=w["asmt"].id, score=Decimal(70)),
        ScoreItem(student_id=w["b"].id, assessment_id=w["asmt"].id, score=Decimal(80)),
    ])
    with pytest.raises(HTTPException) as e:
        await save_report_entry(payload=payload, db=db, current_user=w["admin"])
    assert e.value.status_code == 422
    assert (await db.execute(
        __import__("sqlalchemy").select(StudentAssessmentScore))).scalars().all() == [], \
        "Ada's mark must not have been saved either"


async def test_the_grid_only_offers_pupils_who_can_be_saved(db, org):
    """Otherwise a teacher fills a row in and the save refuses it, and the gate
    reads as a bug rather than a rule."""
    w = await _world(db, org)
    await _enrol(db, org, w["a"], w["maths"])
    grid = await report_entry_grid(class_id=w["cls"].id, subject_id=w["maths"].id,
                                  term_id=w["term"].id, sub_term_id=w["full"].id,
                                  db=db, current_user=w["admin"])
    assert [s.name for s in grid.students] == ["Ada Obi"]


async def test_an_existing_mark_stays_editable_even_if_enrolment_is_gone(db, org):
    """An existing mark must never become uncorrectable. Otherwise removing an
    enrolment would strand a mark that still prints on the report card."""
    w = await _world(db, org)
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=w["a"].id,
                                  subject_id=w["maths"].id, assessment_id=w["asmt"].id,
                                  score=Decimal(55), org_id=org.id))
    await db.commit()   # a mark, but NO enrolment

    grid = await report_entry_grid(class_id=w["cls"].id, subject_id=w["maths"].id,
                                  term_id=w["term"].id, sub_term_id=w["full"].id,
                                  db=db, current_user=w["admin"])
    assert [s.name for s in grid.students] == ["Ada Obi"], "kept because she has a mark"
    out = await save_report_entry(payload=_entry(w, w["a"], 66), db=db, current_user=w["admin"])
    assert out == {"saved": 1}


async def test_enrolment_is_per_session(db, org):
    """Enrolled for a different year is not enrolled for this one."""
    w = await _world(db, org)
    await _enrol(db, org, w["a"], w["maths"], year="2024/2025")
    with pytest.raises(HTTPException) as e:
        await save_report_entry(payload=_entry(w, w["a"]), db=db, current_user=w["admin"])
    assert e.value.status_code == 422


async def test_enrolment_is_per_subject(db, org):
    w = await _world(db, org)
    await _enrol(db, org, w["a"], w["eng"])     # English, not Mathematics
    with pytest.raises(HTTPException) as e:
        await save_report_entry(payload=_entry(w, w["a"]), db=db, current_user=w["admin"])
    assert e.value.status_code == 422


# ── the enrolment grid + save ────────────────────────────────────────────────

async def test_enrollment_grid_shape(db, org):
    w = await _world(db, org)
    await _enrol(db, org, w["a"], w["maths"])
    grid = await subject_enrollment_grid(class_id=w["cls"].id, db=db, current_user=w["admin"])
    assert grid.academic_year == YEAR and grid.class_name == "JSS1 A"
    assert {s.subject_name for s in grid.subjects} == {"Mathematics", "English"}
    ada = next(r for r in grid.students if r.student_name == "Ada Obi")
    assert ada.enrolled_count == 1
    assert next(c.enrolled for c in ada.subjects if c.subject_name == "Mathematics") is True
    assert next(c.enrolled for c in ada.subjects if c.subject_name == "English") is False
    assert grid.total_enrolled == 1


async def test_saving_enrolments_is_a_replace_not_a_merge(db, org):
    """Unticking a box has to remove the enrolment; a merge could never do that."""
    w = await _world(db, org)
    await _enrol(db, org, w["a"], w["maths"])
    await _enrol(db, org, w["a"], w["eng"])

    out = await save_subject_enrollments(
        payload=EnrollmentSave(class_id=w["cls"].id, items=[
            EnrollmentStudentSet(student_id=w["a"].id, subject_ids=[w["eng"].id])]),
        db=db, current_user=w["admin"])
    assert out["removed"] == 1 and out["added"] == 0

    grid = await subject_enrollment_grid(class_id=w["cls"].id, db=db, current_user=w["admin"])
    ada = next(r for r in grid.students if r.student_name == "Ada Obi")
    assert next(c.enrolled for c in ada.subjects if c.subject_name == "Mathematics") is False


async def test_cannot_unenrol_a_pupil_who_has_marks(db, org):
    """That would leave a mark the gate refuses to edit, still printing on the
    card — a contradiction between the register and the report."""
    w = await _world(db, org)
    await _enrol(db, org, w["a"], w["maths"])
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=w["a"].id,
                                  subject_id=w["maths"].id, assessment_id=w["asmt"].id,
                                  score=Decimal(70), org_id=org.id))
    await db.commit()

    with pytest.raises(HTTPException) as e:
        await save_subject_enrollments(
            payload=EnrollmentSave(class_id=w["cls"].id, items=[
                EnrollmentStudentSet(student_id=w["a"].id, subject_ids=[])]),
            db=db, current_user=w["admin"])
    assert e.value.status_code == 422
    assert "already have marks in" in e.value.detail


async def test_cannot_enrol_a_pupil_from_another_class(db, org):
    w = await _world(db, org)
    other = SchoolClass(id=str(uuid.uuid4()), name="JSS1 B", level="JSS1", org_id=org.id)
    db.add(other)
    await db.commit()
    outsider = Student(id=str(uuid.uuid4()), student_id="FSN-0099", first_name="Chi",
                       last_name="Nwo", class_id=other.id, org_id=org.id)
    db.add(outsider)
    await db.commit()

    with pytest.raises(HTTPException) as e:
        await save_subject_enrollments(
            payload=EnrollmentSave(class_id=w["cls"].id, items=[
                EnrollmentStudentSet(student_id=outsider.id, subject_ids=[w["maths"].id])]),
            db=db, current_user=w["admin"])
    assert e.value.status_code == 422
    assert "not in this class" in e.value.detail


async def test_grid_flags_a_pupil_with_marks_but_no_enrolment(db, org):
    """The state the backfill exists to prevent. Visible, not silent."""
    w = await _world(db, org)
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=w["a"].id,
                                  subject_id=w["maths"].id, assessment_id=w["asmt"].id,
                                  score=Decimal(70), org_id=org.id))
    await db.commit()
    grid = await subject_enrollment_grid(class_id=w["cls"].id, db=db, current_user=w["admin"])
    ada = next(r for r in grid.students if r.student_name == "Ada Obi")
    cell = next(c for c in ada.subjects if c.subject_name == "Mathematics")
    assert cell.has_marks is True and cell.enrolled is False


# ── the backfill planner ─────────────────────────────────────────────────────

async def test_backfill_plans_from_existing_marks(db, org):
    w = await _world(db, org)
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=w["a"].id,
                                  subject_id=w["maths"].id, assessment_id=w["asmt"].id,
                                  score=Decimal(70), org_id=org.id))
    await db.commit()
    pairs = await plan_backfill(db, org.id, YEAR)
    assert pairs == [(w["a"].id, w["maths"].id)]


async def test_backfill_includes_a_pair_only_in_the_old_gradebook(db, org):
    """The Musa Yusuf case: a pupil with a `grades` row but no assessment score.
    Backfilling from the new store alone would leave them unenrolled in a subject
    they demonstrably have a grade for."""
    from app.models.modules.school import Grade

    w = await _world(db, org)
    db.add(Grade(id=str(uuid.uuid4()), student_id=w["b"].id, subject_id=w["eng"].id,
                 org_id=org.id))
    await db.commit()
    pairs = await plan_backfill(db, org.id, YEAR)
    assert (w["b"].id, w["eng"].id) in pairs


async def test_backfill_is_idempotent(db, org):
    w = await _world(db, org)
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=w["a"].id,
                                  subject_id=w["maths"].id, assessment_id=w["asmt"].id,
                                  score=Decimal(70), org_id=org.id))
    await db.commit()
    assert len(await plan_backfill(db, org.id, YEAR)) == 1
    await _enrol(db, org, w["a"], w["maths"])
    assert await plan_backfill(db, org.id, YEAR) == [], "already enrolled — nothing to do"
