"""The Performance Tracker: the teacher's Result Analysis view.

Two things are worth pinning here, and neither is the arithmetic — that lives in
`analyse_term`, which the tracker reuses precisely so there is no second opinion
about what a pupil scored:

  1. SCOPING, on the server. A class teacher sees their own class and the subjects
     they teach in it; nobody else does. Hiding a dropdown option is not a check.
  2. BLANKS. An unmarked cell, an unconfigured sub-term and a zero are three
     different claims about a child, and only one of them says they scored nothing.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, Cumulative, CumulativeComponent,
    StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject, Timetable
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import performance_tracker


async def _user(db, org, preset: str) -> User:
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{preset}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=preset.title(), status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _world(db, org, *, marked=True):
    """A class, its teacher, one pupil, one subject, and Autumn Full-Term marked."""
    teacher = await _user(db, org, "teacher")
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary",
                      teacher_id=teacher.id, org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    spring = AcademicTerm(id=str(uuid.uuid4()), name="Spring", position=2, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    db.add_all([cls, subj, autumn, spring, half, full])
    await db.commit()

    pupil = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="Ada",
                    last_name="Obi", class_id=cls.id, org_id=org.id)
    # The teacher teaches this subject in this class — the same Timetable rows
    # Make Report gates mark entry on.
    tt = Timetable(id=str(uuid.uuid4()), class_id=cls.id, subject_id=subj.id,
                   teacher_id=teacher.id, day_of_week=1, start_time="09:00",
                   end_time="10:00", org_id=org.id)
    db.add_all([pupil, tt])
    await db.commit()

    # Autumn FULL-TERM is configured: an assessment inside a TOTAL cumulative.
    a = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", max_score=100,
                   term_id=autumn.id, sub_term_id=full.id, org_id=org.id)
    c = Cumulative(id=str(uuid.uuid4()), name="TOTAL", cumul_type="percentage",
                   term_id=autumn.id, sub_term_id=full.id, org_id=org.id)
    db.add_all([a, c])
    await db.commit()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=c.id,
                               ref_type="assessment", ref_id=a.id, position=0,
                               org_id=org.id))
    if marked:
        db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=pupil.id,
                                      subject_id=subj.id, assessment_id=a.id,
                                      score=72, org_id=org.id))
    await db.commit()
    return dict(teacher=teacher, cls=cls, subj=subj, pupil=pupil,
                autumn=autumn, spring=spring, half=half, full=full)


# ── scoping, enforced on the server ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_class_teacher_sees_their_own_class(db, org):
    w = await _world(db, org)
    res = await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                    db=db, current_user=w["teacher"])
    assert res.class_name == "JSS1 A"
    assert len(res.rows) == 1
    assert res.rows[0].student_name.startswith("Ada")


@pytest.mark.asyncio
async def test_a_teacher_who_is_not_the_class_teacher_is_refused(db, org):
    """The message must name the reason, not present an empty grid: a blank table
    reads as 'this class has no marks', which is a different and wrong answer."""
    w = await _world(db, org)
    intruder = await _user(db, org, "teacher")

    with pytest.raises(HTTPException) as e:
        await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                  db=db, current_user=intruder)
    assert e.value.status_code == 403
    assert "class teacher" in str(e.value.detail).lower()


@pytest.mark.asyncio
async def test_a_class_teacher_cannot_open_a_subject_they_do_not_teach(db, org):
    """Class-teacher access is not subject access. The tracker is per subject, and
    the subject set is the one Make Report gates mark entry on."""
    w = await _world(db, org)
    other = Subject(id=str(uuid.uuid4()), name="French", org_id=org.id)
    db.add(other)
    await db.commit()

    with pytest.raises(HTTPException) as e:
        await performance_tracker(class_id=w["cls"].id, subject_id=other.id,
                                  db=db, current_user=w["teacher"])
    assert e.value.status_code == 403
    assert "teach this subject" in str(e.value.detail).lower()


@pytest.mark.asyncio
async def test_an_admin_may_open_any_class(db, org):
    w = await _world(db, org)
    admin = await _user(db, org, "org_admin")
    res = await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                    db=db, current_user=admin)
    assert len(res.rows) == 1


@pytest.mark.asyncio
async def test_a_class_with_no_class_teacher_says_so(db, org):
    """Distinguished from 'someone else teaches them': telling a teacher it is not
    them sends them looking for a colleague who does not exist."""
    w = await _world(db, org)
    orphan = SchoolClass(id=str(uuid.uuid4()), name="Playgroup", level="Early Years",
                         teacher_id=None, org_id=org.id)
    db.add(orphan)
    await db.commit()

    with pytest.raises(HTTPException) as e:
        await performance_tracker(class_id=orphan.id, subject_id=w["subj"].id,
                                  db=db, current_user=w["teacher"])
    assert e.value.status_code == 403
    assert "no class teacher assigned" in str(e.value.detail).lower()


# ── the cells, which must never overstate what is known ───────────────────────

@pytest.mark.asyncio
async def test_a_marked_cell_carries_its_score_and_grade(db, org):
    w = await _world(db, org)
    res = await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                    db=db, current_user=w["teacher"])
    key = f"{w['autumn'].id}:{w['full'].id}"
    cell = res.rows[0].cells[key]
    assert cell.score == 72
    assert cell.grade


@pytest.mark.asyncio
async def test_an_unmarked_pupil_reads_as_blank_not_zero(db, org):
    """The whole point of the column. A dash means 'not entered'; a 0 would be a
    mark this child did not receive, printed next to their name."""
    w = await _world(db, org, marked=False)
    res = await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                    db=db, current_user=w["teacher"])
    key = f"{w['autumn'].id}:{w['full'].id}"
    cell = res.rows[0].cells[key]
    assert cell.score is None, "an unmarked cell must be empty"
    assert cell.grade is None


@pytest.mark.asyncio
async def test_a_sub_term_with_no_cumulative_of_its_own_is_not_computed(db, org):
    """`_pick_display_cumulative` falls back to ANY cumulative when none matches the
    sub-term — fine for one report card, wrong here, because it made the Half-Term
    column repeat the Full-Term mark and assert a score nobody recorded."""
    w = await _world(db, org)
    res = await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                    db=db, current_user=w["teacher"])

    by_key = {c.key: c for c in res.columns}
    half_key = f"{w['autumn'].id}:{w['half'].id}"
    full_key = f"{w['autumn'].id}:{w['full'].id}"
    assert by_key[half_key].available is False
    assert by_key[full_key].available is True
    assert res.rows[0].cells[half_key].score is None, (
        "Half-Term has no cumulative, so it must be blank rather than borrowing "
        "Full-Term's number")


@pytest.mark.asyncio
async def test_the_columns_come_out_in_teaching_order(db, org):
    """Every term's `position` is 0 in production, so the order cannot come from
    there; the printed report still has to read Autumn, Spring, Summer."""
    w = await _world(db, org)
    res = await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                    db=db, current_user=w["teacher"])

    assert res.columns[0].key == "promotional"
    groups = [c.group for c in res.columns if c.group]
    assert groups.index("Autumn") < groups.index("Spring")
    # Mock is a Spring-only column, and is a DISPLAY rule: sub-terms are org-wide.
    spring_labels = [c.label for c in res.columns if c.group == "Spring"]
    autumn_labels = [c.label for c in res.columns if c.group == "Autumn"]
    assert "Mock" in spring_labels
    assert "Mock" not in autumn_labels


@pytest.mark.asyncio
async def test_the_sessional_score_stays_blank_on_a_single_term(db, org):
    """Only Autumn has marks. A 'sessional' figure from one term would present a
    term average as though the year were over."""
    w = await _world(db, org)
    res = await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                    db=db, current_user=w["teacher"])
    row = res.rows[0]
    assert row.sessional_terms_counted == 1
    assert row.sessional_score is None
    assert row.sessional_grade is None


@pytest.mark.asyncio
async def test_configuring_a_half_term_cumulative_fills_the_column_with_no_code_change(db, org):
    """The column layout is the school's reporting shape; what fills it is the
    school's configuration. So the fix for an empty Half-Term column is to
    configure Half-Term — not to edit this endpoint.

    The same run asserts the other half of the contract: Spring's Half-Term, which
    exists as a sub-term but has no cumulative, still reads as a dash. One term
    being set up must not make another look marked.
    """
    w = await _world(db, org)

    # Before: Autumn Half-Term has no cumulative of its own.
    before = await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                       db=db, current_user=w["teacher"])
    half_key = f"{w['autumn'].id}:{w['half'].id}"
    assert {c.key: c.available for c in before.columns}[half_key] is False
    assert before.rows[0].cells[half_key].score is None

    # Configure Half-Term exactly as Full-Term is configured, and mark the pupil.
    ha = Assessment(id=str(uuid.uuid4()), name="CA 1", max_score=100,
                    term_id=w["autumn"].id, sub_term_id=w["half"].id, org_id=org.id)
    hc = Cumulative(id=str(uuid.uuid4()), name="TOTAL", cumul_type="percentage",
                    term_id=w["autumn"].id, sub_term_id=w["half"].id, org_id=org.id)
    db.add_all([ha, hc])
    await db.commit()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=hc.id,
                               ref_type="assessment", ref_id=ha.id, position=0,
                               org_id=org.id))
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=w["pupil"].id,
                                  subject_id=w["subj"].id, assessment_id=ha.id,
                                  score=58, org_id=org.id))
    await db.commit()

    after = await performance_tracker(class_id=w["cls"].id, subject_id=w["subj"].id,
                                      db=db, current_user=w["teacher"])
    cols = {c.key: c for c in after.columns}
    assert cols[half_key].available is True, "configuring it must make it computable"
    cell = after.rows[0].cells[half_key]
    assert cell.score == 58, "the Half-Term column now carries its OWN mark"
    assert cell.grade

    # Full-Term is untouched and still its own figure — not overwritten, not shared.
    full_key = f"{w['autumn'].id}:{w['full'].id}"
    assert after.rows[0].cells[full_key].score == 72

    # And a sub-term that still has no cumulative stays a dash.
    spring_half_key = f"{w['spring'].id}:{w['half'].id}"
    assert cols[spring_half_key].available is False
    assert after.rows[0].cells[spring_half_key].score is None, (
        "Spring has no cumulative; configuring Autumn must not make Spring look marked")
