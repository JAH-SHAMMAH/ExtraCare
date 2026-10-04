"""The tracker's "Average Score" option — subject_id omitted.

Confirmed against Educare: it is the FIRST option in the same dropdown as the
subjects, selected the same way one is, and it shows the cross-subject average
instead of one subject's marks. So it is the omitted-`subject_id` case, not a
separate control or a different metric.

THE INVARIANT THAT MATTERS: it reuses `PupilResult.average` — the mean the
shared analysis core already computes — rather than a second average computed in
the tracker. Verified against production as identical to the report card for 25
of 25 pupils, and pinned here against Order of Merit, which ranks on the same
figure. A second implementation would be free to drift from both.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, AcademicTerm, Assessment, Cumulative,
    CumulativeComponent, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject, Timetable
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import performance_tracker
from tests.conftest import ensure_section

pytestmark = pytest.mark.asyncio


async def _user(db, org, preset: str, name: str) -> User:
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{name}-{uuid.uuid4().hex[:6]}@x.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


class W:
    pass


async def _world(db, org):
    w = W()
    w.admin = await _user(db, org, "org_admin", "Admin")
    w.class_teacher = await _user(db, org, "teacher", "Class Teacher")
    w.subject_only = await _user(db, org, "teacher", "Subject Only")

    w.sess = AcademicSession(id=str(uuid.uuid4()), name="2025/2026",
                             start_date=date(2025, 9, 15), end_date=date(2026, 7, 10),
                             is_current=True, org_id=org.id)
    w.autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    w.full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    w.cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1",
                        teacher_id=w.class_teacher.id, org_id=org.id)
    _sec = await ensure_section(db, org)
    w.maths = Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=_sec.id, org_id=org.id)
    w.eng = Subject(id=str(uuid.uuid4()), name="English Language", section_id=_sec.id, org_id=org.id)
    db.add_all([w.sess, w.autumn, w.full, w.cls, w.maths, w.eng])
    await db.commit()

    for subj, who in ((w.maths, w.class_teacher), (w.eng, w.subject_only)):
        db.add(Timetable(id=str(uuid.uuid4()), class_id=w.cls.id, subject_id=subj.id,
                         day_of_week=0, start_time="08:00", end_time="09:00",
                         teacher_id=who.id, org_id=org.id))
    w.pupil = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                      last_name="Obi", class_id=w.cls.id, org_id=org.id)
    db.add(w.pupil)
    await db.commit()

    # One out-of-100 EXAM and a percentage TOTAL over it, for Autumn.
    w.exam = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=Decimal("100"),
                        session_id=w.sess.id, term_id=w.autumn.id,
                        sub_term_id=w.full.id, org_id=org.id)
    db.add(w.exam)
    await db.commit()
    c = Cumulative(id=str(uuid.uuid4()), name="TOTAL", cumul_type="percentage",
                   session_id=w.sess.id, term_id=w.autumn.id,
                   sub_term_id=w.full.id, org_id=org.id)
    db.add(c)
    await db.commit()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=c.id,
                               ref_type="assessment", ref_id=w.exam.id, position=0,
                               org_id=org.id))
    await db.commit()
    return w


async def _mark(db, org, w, subject, score):
    db.add(StudentAssessmentScore(
        id=str(uuid.uuid4()), student_id=w.pupil.id, subject_id=subject.id,
        assessment_id=w.exam.id, score=Decimal(score), source="entry", org_id=org.id))
    await db.commit()


def _autumn_cell(r, w):
    key = f"{w.autumn.id}:{w.full.id}"
    return r.rows[0].cells[key]


# ── the invariant ────────────────────────────────────────────────────────────

async def test_the_average_is_the_core_s_own_figure_not_a_second_one(db, org):
    """80 in Mathematics and 60 in English -> 70. Pinned against Order of Merit,
    which ranks on `PupilResult.average`: if the tracker computed its own mean
    the two could drift, and this is the test that would catch it."""
    from app.routers.modules.platform import order_of_merit

    w = await _world(db, org)
    await _mark(db, org, w, w.maths, 80)
    await _mark(db, org, w, w.eng, 60)

    r = await performance_tracker(class_id=w.cls.id, db=db, current_user=w.admin)
    assert r.is_average is True
    assert r.subject_id is None
    assert r.subject_name == "Average Score", "the dropdown's own label"
    assert _autumn_cell(r, w).score == Decimal("70.00")

    merit = await order_of_merit(term_id=w.autumn.id, sub_term_id=w.full.id,
                                class_id=w.cls.id, db=db, current_user=w.admin)
    assert merit.rows[0].average == Decimal("70.00"), (
        "the same pupil, the same figure, from the same core")


async def test_naming_a_subject_still_shows_that_subject_alone(db, org):
    """The existing behaviour must be untouched — this adds an option, it does
    not change the ones already there."""
    w = await _world(db, org)
    await _mark(db, org, w, w.maths, 80)
    await _mark(db, org, w, w.eng, 60)

    r = await performance_tracker(class_id=w.cls.id, subject_id=w.maths.id,
                                  db=db, current_user=w.admin)
    assert r.is_average is False
    assert r.subject_id == w.maths.id and r.subject_name == "Mathematics"
    assert _autumn_cell(r, w).score == Decimal("80.00"), "Maths alone, not the mean"


async def test_a_partially_marked_subject_is_excluded_from_the_average(db, org):
    """The core leaves an incomplete subject out of `average` rather than folding
    it in at a deflated value, and the Average Score column inherits that."""
    w = await _world(db, org)
    # a second component nobody marks, making English incomplete
    ca = Assessment(id=str(uuid.uuid4()), name="CA", max_score=Decimal("100"),
                    session_id=w.sess.id, term_id=w.autumn.id,
                    sub_term_id=w.full.id, org_id=org.id)
    db.add(ca)
    await db.commit()
    cum = (await db.execute(
        __import__("sqlalchemy").select(Cumulative).where(
            Cumulative.term_id == w.autumn.id))).scalars().first()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=cum.id,
                               ref_type="assessment", ref_id=ca.id, position=1,
                               org_id=org.id))
    await db.commit()

    await _mark(db, org, w, w.maths, 80)
    db.add(StudentAssessmentScore(
        id=str(uuid.uuid4()), student_id=w.pupil.id, subject_id=w.maths.id,
        assessment_id=ca.id, score=Decimal(80), source="entry", org_id=org.id))
    await _mark(db, org, w, w.eng, 60)        # EXAM only — English is incomplete
    await db.commit()

    r = await performance_tracker(class_id=w.cls.id, db=db, current_user=w.admin)
    # Maths is complete (80 + 80 of 200 = 80%); English is not and is excluded.
    assert _autumn_cell(r, w).score == Decimal("80.00"), (
        "an unmarked component must not drag the average down")


async def test_an_unmarked_pupil_has_an_empty_cell_not_a_zero(db, org):
    w = await _world(db, org)
    r = await performance_tracker(class_id=w.cls.id, db=db, current_user=w.admin)
    cell = _autumn_cell(r, w)
    assert cell.score is None and cell.grade is None


# ── access ───────────────────────────────────────────────────────────────────

async def test_the_class_teacher_may_open_the_average(db, org):
    """Not a widening: Order of Merit already shows a class teacher their own
    class's overall averages through the same class gate."""
    w = await _world(db, org)
    await _mark(db, org, w, w.maths, 80)
    await _mark(db, org, w, w.eng, 60)

    r = await performance_tracker(class_id=w.cls.id, db=db,
                                  current_user=w.class_teacher)
    assert r.is_average is True
    assert _autumn_cell(r, w).score == Decimal("70.00"), (
        "including English, which they do not teach — it is an average, and the "
        "class gate is what grants it")


async def test_a_subject_only_teacher_is_refused_the_tracker_entirely(db, org):
    """They teach English in this class but are not its class teacher, so the
    class gate refuses them — for the average AND for the subject they teach.

    That is pre-existing and deliberate, not a side effect of this change:
    `result_analysis_classes` states it outright — "this is NOT 'classes I teach
    in'… Result Analysis is a class teacher's view of their own class". The
    Average Score option inherits that gate rather than opening a new door
    through it.
    """
    w = await _world(db, org)
    for subject_id in (None, w.eng.id):
        with pytest.raises(HTTPException) as e:
            await performance_tracker(class_id=w.cls.id, subject_id=subject_id,
                                      db=db, current_user=w.subject_only)
        assert e.value.status_code == 403, f"subject_id={subject_id}"


async def test_a_bad_subject_id_is_still_404_not_treated_as_average(db, org):
    """Omitting the parameter means the average; passing a nonsense one is an
    error. Collapsing the two would turn a typo into a different report."""
    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await performance_tracker(class_id=w.cls.id, subject_id=str(uuid.uuid4()),
                                  db=db, current_user=w.admin)
    assert e.value.status_code == 404
