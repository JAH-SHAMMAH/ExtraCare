"""Per-subject report comments (SubjectReportComment).

Driven as the real roles. The comment a subject teacher writes answers to
`_teacher_assignments` — whoever may enter the subject's marks — and NOT to
`_gate_comment_access`, which governs the card's two fixed slots and is left
untouched: head stays admin-only, pc stays PC-teacher-only.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, AssessmentGroup, Cumulative,
    CumulativeComponent, GradingBand, GradingScale, ReportCommentType,
    StudentAssessmentScore, SubjectReportComment,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import (
    report_card, save_subject_comments, subject_comment_grid,
)
from app.schemas.platform import SubjectCommentItem, SubjectCommentSave

pytestmark = pytest.mark.asyncio

TEACHER_PERMS = ["school:reports:read", "school:reports:write", "school:read"]


async def _user(db, org, slug, perms, name):
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@x.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    r = Role(id=str(uuid.uuid4()), name=slug, slug=slug, permissions=perms,
             org_id=org.id, is_system=False)
    db.add(r)
    u.roles = [r]
    db.add(u)
    await db.commit()
    return u


async def _world(db, org):
    pc = await _user(db, org, "teacher", TEACHER_PERMS, "Pc Teacher")
    maths_t = await _user(db, org, "teacher", TEACHER_PERMS, "Maths Teacher")
    eng_t = await _user(db, org, "teacher", TEACHER_PERMS, "English Teacher")
    admin = await _user(db, org, "super_user", ["*"], "Officer")

    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1",
                      teacher_id=pc.id, org_id=org.id)
    other = SchoolClass(id=str(uuid.uuid4()), name="JSS1 B", level="JSS1", org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", teacher_id=maths_t.id, org_id=org.id)
    eng = Subject(id=str(uuid.uuid4()), name="English", teacher_id=eng_t.id, org_id=org.id)
    a = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                last_name="Obi", class_id=cls.id, org_id=org.id)
    b = Student(id=str(uuid.uuid4()), student_id="FSN-0002", first_name="Bola",
                last_name="Eze", class_id=cls.id, org_id=org.id)
    outsider = Student(id=str(uuid.uuid4()), student_id="FSN-0003", first_name="Chidi",
                       last_name="Nwo", class_id=other.id, org_id=org.id)
    grp = AssessmentGroup(id=str(uuid.uuid4()), name="CBT", position=0, org_id=org.id)
    db.add_all([term, full, cls, other, maths, eng, a, b, outsider, grp])
    await db.commit()
    asmt = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", code="CBT",
                      max_score=Decimal("100"), term_id=term.id, sub_term_id=full.id,
                      group_id=grp.id, decimal_places=0, position=0, org_id=org.id)
    db.add(asmt)
    await db.commit()
    return dict(pc=pc, maths_t=maths_t, eng_t=eng_t, admin=admin, term=term, full=full,
                cls=cls, maths=maths, eng=eng, a=a, b=b, outsider=outsider, asmt=asmt)


def _save(w, subject, items):
    return SubjectCommentSave(class_id=w["cls"].id, subject_id=subject.id,
                              term_id=w["term"].id, sub_term_id=w["full"].id,
                              items=items)


# ── writing ──────────────────────────────────────────────────────────────────

async def test_subject_teacher_writes_a_remark_for_their_own_subject(db, org):
    w = await _world(db, org)
    out = await save_subject_comments(
        payload=_save(w, w["maths"], [SubjectCommentItem(student_id=w["a"].id,
                                                         text="Strong on algebra.")]),
        db=db, current_user=w["maths_t"])
    assert out == {"saved": 1, "cleared": 0}

    grid = await subject_comment_grid(class_id=w["cls"].id, subject_id=w["maths"].id,
                                     term_id=w["term"].id, sub_term_id=w["full"].id,
                                     db=db, current_user=w["maths_t"])
    by = {r.student_name: r.text for r in grid.rows}
    assert by["Ada Obi"] == "Strong on algebra."
    assert by["Bola Eze"] is None
    assert grid.subject_name == "Mathematics" and grid.class_name == "JSS1 A"


async def test_another_subjects_teacher_is_refused(db, org):
    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await save_subject_comments(
            payload=_save(w, w["eng"], [SubjectCommentItem(student_id=w["a"].id, text="x")]),
            db=db, current_user=w["maths_t"])
    assert e.value.status_code == 403
    assert "do not teach this subject" in e.value.detail


async def test_reading_the_grid_is_gated_too(db, org):
    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await subject_comment_grid(class_id=w["cls"].id, subject_id=w["eng"].id,
                                   term_id=w["term"].id, sub_term_id=w["full"].id,
                                   db=db, current_user=w["maths_t"])
    assert e.value.status_code == 403


async def test_a_pupil_from_another_class_cannot_be_commented_on(db, org):
    """The teacher legitimately teaches this (class, subject); passing a pupil id
    from a different class must not let them write onto that pupil's card."""
    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await save_subject_comments(
            payload=_save(w, w["maths"],
                          [SubjectCommentItem(student_id=w["outsider"].id, text="x")]),
            db=db, current_user=w["maths_t"])
    assert e.value.status_code == 422
    assert "not in this class" in e.value.detail


async def test_blank_text_clears_the_row_rather_than_storing_empty(db, org):
    """A stored "" prints as nothing on the card but reads as a comment in the
    grid — the two must not disagree."""
    w = await _world(db, org)
    await save_subject_comments(
        payload=_save(w, w["maths"], [SubjectCommentItem(student_id=w["a"].id, text="First go")]),
        db=db, current_user=w["maths_t"])

    out = await save_subject_comments(
        payload=_save(w, w["maths"], [SubjectCommentItem(student_id=w["a"].id, text="   ")]),
        db=db, current_user=w["maths_t"])
    assert out == {"saved": 0, "cleared": 1}

    rows = (await db.execute(
        __import__("sqlalchemy").select(SubjectReportComment).where(
            SubjectReportComment.org_id == org.id))).scalars().all()
    assert rows == []


async def test_editing_a_remark_updates_in_place(db, org):
    w = await _world(db, org)
    for text in ("First", "Second"):
        await save_subject_comments(
            payload=_save(w, w["maths"], [SubjectCommentItem(student_id=w["a"].id, text=text)]),
            db=db, current_user=w["maths_t"])
    rows = (await db.execute(
        __import__("sqlalchemy").select(SubjectReportComment).where(
            SubjectReportComment.org_id == org.id))).scalars().all()
    assert len(rows) == 1 and rows[0].text == "Second"
    assert rows[0].recorded_by == w["maths_t"].id


async def test_two_subjects_keep_separate_remarks_for_one_pupil(db, org):
    """The whole point of the subject dimension."""
    w = await _world(db, org)
    await save_subject_comments(
        payload=_save(w, w["maths"], [SubjectCommentItem(student_id=w["a"].id, text="Maths note")]),
        db=db, current_user=w["maths_t"])
    await save_subject_comments(
        payload=_save(w, w["eng"], [SubjectCommentItem(student_id=w["a"].id, text="English note")]),
        db=db, current_user=w["eng_t"])

    m = await subject_comment_grid(class_id=w["cls"].id, subject_id=w["maths"].id,
                                   term_id=w["term"].id, sub_term_id=w["full"].id,
                                   db=db, current_user=w["maths_t"])
    e = await subject_comment_grid(class_id=w["cls"].id, subject_id=w["eng"].id,
                                   term_id=w["term"].id, sub_term_id=w["full"].id,
                                   db=db, current_user=w["eng_t"])
    assert next(r.text for r in m.rows if r.student_id == w["a"].id) == "Maths note"
    assert next(r.text for r in e.rows if r.student_id == w["a"].id) == "English note"


async def test_max_length_is_enforced_when_configured(db, org):
    w = await _world(db, org)
    db.add(ReportCommentType(id=str(uuid.uuid4()), name="Subject Teacher Comment",
                             comment_type="short", max_length=20, org_id=org.id))
    await db.commit()

    grid = await subject_comment_grid(class_id=w["cls"].id, subject_id=w["maths"].id,
                                     term_id=w["term"].id, sub_term_id=w["full"].id,
                                     db=db, current_user=w["maths_t"])
    assert grid.max_length == 20

    with pytest.raises(HTTPException) as e:
        await save_subject_comments(
            payload=_save(w, w["maths"],
                          [SubjectCommentItem(student_id=w["a"].id, text="x" * 21)]),
            db=db, current_user=w["maths_t"])
    assert e.value.status_code == 422
    assert "20-character limit" in e.value.detail


async def test_has_marks_flags_who_was_actually_assessed(db, org):
    w = await _world(db, org)
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=w["a"].id,
                                  subject_id=w["maths"].id, assessment_id=w["asmt"].id,
                                  score=Decimal("70"), org_id=org.id))
    await db.commit()
    grid = await subject_comment_grid(class_id=w["cls"].id, subject_id=w["maths"].id,
                                     term_id=w["term"].id, sub_term_id=w["full"].id,
                                     db=db, current_user=w["maths_t"])
    by = {r.student_name: r.has_marks for r in grid.rows}
    assert by == {"Ada Obi": True, "Bola Eze": False}


# ── the card ─────────────────────────────────────────────────────────────────

async def _gradeable(db, org, w):
    """Marks + a TOTAL cumulative, so report_card produces a subject row at all."""
    sc = GradingScale(id=str(uuid.uuid4()), name="GRADING SCALE", scale_type="numeric",
                      is_provisional=False, purpose="grade", show_in_table=True, org_id=org.id)
    db.add(sc)
    await db.flush()
    for g, lo, hi in [("C", 70, 79), ("F", 0, 39)]:
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade=g, remark=g,
                           min_score=Decimal(lo), max_score=Decimal(hi), org_id=org.id))
    cum = Cumulative(id=str(uuid.uuid4()), name="TOTAL", term_id=w["term"].id,
                     sub_term_id=w["full"].id, cumul_type="percentage",
                     decimal_places=2, position=0, org_id=org.id)
    db.add(cum)
    await db.flush()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=cum.id,
                               ref_type="assessment", ref_id=w["asmt"].id,
                               position=0, org_id=org.id))
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=w["a"].id,
                                  subject_id=w["maths"].id, assessment_id=w["asmt"].id,
                                  score=Decimal("75"), org_id=org.id))
    await db.commit()


async def test_the_remark_reaches_the_report_card(db, org):
    w = await _world(db, org)
    await _gradeable(db, org, w)
    await save_subject_comments(
        payload=_save(w, w["maths"], [SubjectCommentItem(student_id=w["a"].id,
                                                         text="Excellent progress.")]),
        db=db, current_user=w["maths_t"])

    card = await report_card(student_id=w["a"].id, term_id=w["term"].id,
                            sub_term_id=w["full"].id, db=db, current_user=w["admin"])
    row = next(r for r in card.subjects if r.subject_name == "Mathematics")
    assert row.comment == "Excellent progress."


async def test_a_remark_does_not_leak_across_sub_terms(db, org):
    w = await _world(db, org)
    await _gradeable(db, org, w)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=0, org_id=org.id)
    db.add(half)
    await db.commit()
    await save_subject_comments(
        payload=_save(w, w["maths"], [SubjectCommentItem(student_id=w["a"].id, text="Full-term only")]),
        db=db, current_user=w["maths_t"])

    card = await report_card(student_id=w["a"].id, term_id=w["term"].id,
                            sub_term_id=half.id, db=db, current_user=w["admin"])
    for row in card.subjects:
        assert row.comment is None, "a Full-Term remark appeared on the Half-Term card"


async def test_head_and_pc_slots_are_untouched_by_this(db, org):
    """The invariant. _gate_comment_access keeps its meaning: a subject teacher
    writing a subject remark gains no access to the card's head/pc slots."""
    from app.routers.modules.platform import _gate_comment_access

    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await _gate_comment_access(db, org.id, w["maths_t"], w["cls"].id, "head")
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        await _gate_comment_access(db, org.id, w["maths_t"], w["cls"].id, "pc")
    assert e.value.status_code == 403
    # and the PC teacher still passes for pc
    await _gate_comment_access(db, org.id, w["pc"], w["cls"].id, "pc")
