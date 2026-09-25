"""Per-subject report sign-off (SubjectReportSubmission).

Driven as the REAL roles, not a permissive admin: a subject teacher signing off
their own subject, a second subject teacher who must not be able to sign off the
first one's, and the PC teacher reading the readiness grid. A test that only ever
calls these as an admin would pass with the gates inverted.

The central invariant: ReportApproval keeps its meaning. It is unique on
(class, term) and stays PC-teacher-only; these endpoints add a finer grain
beside it and must not gate it, or a class holding a teacherless subject could
never be submitted at all.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.modules.academics import ReportApproval, SubjectReportSubmission
from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, AssessmentGroup, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.academics import (
    submit_class_report, submit_subject_report, subject_readiness,
    withdraw_subject_report,
)
from app.schemas.academics import ReportSubmitRequest, SubjectSubmitRequest

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
    """A class with two subjects, each with its own teacher, plus a PC teacher.

    Subject.teacher_id is the assignment route in play (the Timetable is empty),
    which is the production situation today.
    """
    pc = await _user(db, org, "teacher", TEACHER_PERMS, "Pc Teacher")
    maths_t = await _user(db, org, "teacher", TEACHER_PERMS, "Maths Teacher")
    eng_t = await _user(db, org, "teacher", TEACHER_PERMS, "English Teacher")
    admin = await _user(db, org, "super_user", ["*"], "Officer")

    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1",
                      teacher_id=pc.id, org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", teacher_id=maths_t.id, org_id=org.id)
    eng = Subject(id=str(uuid.uuid4()), name="English", teacher_id=eng_t.id, org_id=org.id)
    pupil = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                    last_name="Obi", class_id=cls.id, org_id=org.id)
    grp = AssessmentGroup(id=str(uuid.uuid4()), name="CBT", position=0, org_id=org.id)
    db.add_all([term, full, cls, maths, eng, pupil, grp])
    await db.commit()
    asmt = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", code="CBT",
                      max_score=Decimal("100"), term_id=term.id, sub_term_id=full.id,
                      group_id=grp.id, decimal_places=0, position=0, org_id=org.id)
    db.add(asmt)
    await db.commit()
    return dict(pc=pc, maths_t=maths_t, eng_t=eng_t, admin=admin, term=term, full=full,
                cls=cls, maths=maths, eng=eng, pupil=pupil, asmt=asmt)


async def _mark(db, org, w, subject, score=70):
    db.add(StudentAssessmentScore(
        id=str(uuid.uuid4()), student_id=w["pupil"].id, subject_id=subject.id,
        assessment_id=w["asmt"].id, score=Decimal(score), org_id=org.id))
    await db.commit()


def _req(w, subject):
    return SubjectSubmitRequest(class_id=w["cls"].id, subject_id=subject.id,
                                term_id=w["term"].id, sub_term_id=w["full"].id)


# ── submitting ───────────────────────────────────────────────────────────────

async def test_subject_teacher_signs_off_their_own_subject(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])

    out = await submit_subject_report(payload=_req(w, w["maths"]), db=db,
                                     current_user=w["maths_t"])

    assert out.subject_name == "Mathematics"
    assert out.class_name == "JSS1 A"
    assert out.submitted_by == w["maths_t"].id
    assert out.submitted_by_name == "Maths Teacher"
    assert out.score_count == 1
    assert out.submitted_at is not None


async def test_a_subject_with_no_marks_cannot_be_signed_off(db, org):
    """A sign-off attests the work is done. Allowing one on an empty subject
    would show the PC teacher green for marks that were never entered."""
    w = await _world(db, org)

    with pytest.raises(HTTPException) as e:
        await submit_subject_report(payload=_req(w, w["maths"]), db=db,
                                    current_user=w["maths_t"])
    assert e.value.status_code == 422
    assert "No marks have been entered" in e.value.detail


async def test_one_subject_teacher_cannot_sign_off_anothers_subject(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["eng"])

    with pytest.raises(HTTPException) as e:
        await submit_subject_report(payload=_req(w, w["eng"]), db=db,
                                    current_user=w["maths_t"])
    assert e.value.status_code == 403
    assert "do not teach" in e.value.detail


async def test_double_submission_is_refused_and_names_who_did_it(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    await submit_subject_report(payload=_req(w, w["maths"]), db=db, current_user=w["maths_t"])

    with pytest.raises(HTTPException) as e:
        await submit_subject_report(payload=_req(w, w["maths"]), db=db,
                                    current_user=w["maths_t"])
    assert e.value.status_code == 409
    assert "Maths Teacher" in e.value.detail


async def test_admin_may_sign_off_on_a_teachers_behalf(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    out = await submit_subject_report(payload=_req(w, w["maths"]), db=db,
                                     current_user=w["admin"])
    assert out.submitted_by == w["admin"].id


# ── withdrawing ──────────────────────────────────────────────────────────────

async def test_submitter_can_withdraw_and_then_resubmit(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    out = await submit_subject_report(payload=_req(w, w["maths"]), db=db,
                                     current_user=w["maths_t"])

    await withdraw_subject_report(submission_id=out.id, db=db, current_user=w["maths_t"])
    assert (await db.get(SubjectReportSubmission, out.id)) is None

    again = await submit_subject_report(payload=_req(w, w["maths"]), db=db,
                                       current_user=w["maths_t"])
    assert again.id != out.id


async def test_another_teacher_cannot_withdraw_someone_elses_signoff(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    out = await submit_subject_report(payload=_req(w, w["maths"]), db=db,
                                      current_user=w["maths_t"])

    with pytest.raises(HTTPException) as e:
        await withdraw_subject_report(submission_id=out.id, db=db, current_user=w["eng_t"])
    assert e.value.status_code == 403
    assert (await db.get(SubjectReportSubmission, out.id)) is not None


async def test_withdrawal_refused_once_the_class_report_has_moved_on(db, org):
    """After the PC teacher hands the class to the office, a subject quietly
    becoming unsubmitted would change what that submission meant."""
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    out = await submit_subject_report(payload=_req(w, w["maths"]), db=db,
                                     current_user=w["maths_t"])
    await submit_class_report(
        payload=ReportSubmitRequest(class_id=w["cls"].id, term="Autumn"),
        db=db, current_user=w["pc"])

    with pytest.raises(HTTPException) as e:
        await withdraw_subject_report(submission_id=out.id, db=db, current_user=w["maths_t"])
    assert e.value.status_code == 409
    assert "submitted" in e.value.detail


# ── the readiness grid ───────────────────────────────────────────────────────

async def test_readiness_distinguishes_unsigned_from_unmarked(db, org):
    """Three states, because they call for different actions: signed off, marks
    in but unsigned, and nothing entered at all."""
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    await _mark(db, org, w, w["eng"])
    await submit_subject_report(payload=_req(w, w["maths"]), db=db, current_user=w["maths_t"])

    grid = await subject_readiness(class_id=w["cls"].id, term_id=w["term"].id,
                                  sub_term_id=w["full"].id, db=db, current_user=w["pc"])

    assert grid.total_count == 2 and grid.submitted_count == 1
    by_name = {r.subject_name: r for r in grid.subjects}
    assert by_name["Mathematics"].submitted is True
    assert by_name["Mathematics"].submitted_by_name == "Maths Teacher"
    assert by_name["English"].submitted is False
    assert by_name["English"].score_count == 1, "marks are in, just unsigned"
    assert by_name["English"].teacher_name == "English Teacher", "who to chase"


async def test_readiness_names_the_expected_teacher_for_an_unstarted_subject(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])

    grid = await subject_readiness(class_id=w["cls"].id, term_id=w["term"].id,
                                  sub_term_id=w["full"].id, db=db, current_user=w["pc"])
    # English has no marks at all, so it is not in the derived set yet -- there is
    # no class-to-subject table to know it was expected. Documented, not asserted
    # as desirable: the Timetable is what supplies that, and it is empty here.
    assert [r.subject_name for r in grid.subjects] == ["Mathematics"]


async def test_a_subject_teacher_can_read_the_grid_for_a_class_they_teach(db, org):
    """How a teacher finds out their own subject is holding the class up."""
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])

    grid = await subject_readiness(class_id=w["cls"].id, term_id=w["term"].id,
                                  sub_term_id=w["full"].id, db=db, current_user=w["maths_t"])
    assert grid.total_count == 1


async def test_an_unrelated_teacher_cannot_read_the_grid(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    outsider = await _user(db, org, "teacher", TEACHER_PERMS, "Outside Teacher")

    with pytest.raises(HTTPException) as e:
        await subject_readiness(class_id=w["cls"].id, term_id=w["term"].id,
                                sub_term_id=w["full"].id, db=db, current_user=outsider)
    assert e.value.status_code == 403


async def test_readiness_reports_the_class_stage_too(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    grid = await subject_readiness(class_id=w["cls"].id, term_id=w["term"].id,
                                  sub_term_id=w["full"].id, db=db, current_user=w["pc"])
    assert grid.class_stage is None, "no workflow row opened yet"

    await submit_class_report(
        payload=ReportSubmitRequest(class_id=w["cls"].id, term="Autumn"),
        db=db, current_user=w["pc"])
    grid = await subject_readiness(class_id=w["cls"].id, term_id=w["term"].id,
                                  sub_term_id=w["full"].id, db=db, current_user=w["pc"])
    assert grid.class_stage == "submitted"


# ── the invariant: ReportApproval is unchanged ───────────────────────────────

async def test_class_submit_is_not_gated_on_subject_signoffs(db, org):
    """THE load-bearing test. If this ever starts failing because someone added a
    gate, a class holding a subject with no assigned teacher becomes impossible
    to submit -- nobody may sign that subject off, so the class report would be
    stuck forever. Advisory by design.
    """
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    await _mark(db, org, w, w["eng"])
    # Nothing signed off at all.

    out = await submit_class_report(
        payload=ReportSubmitRequest(class_id=w["cls"].id, term="Autumn"),
        db=db, current_user=w["pc"])

    assert out.stage == "submitted"


async def test_subject_signoff_does_not_touch_the_approval_row(db, org):
    w = await _world(db, org)
    await _mark(db, org, w, w["maths"])
    await submit_subject_report(payload=_req(w, w["maths"]), db=db, current_user=w["maths_t"])

    rows = (await db.execute(
        __import__("sqlalchemy").select(ReportApproval).where(
            ReportApproval.org_id == org.id))).scalars().all()
    assert rows == [], "a subject sign-off must not open a class workflow row"
