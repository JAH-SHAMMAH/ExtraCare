"""Tests for Result Publishing — the draft/published gate on grades.

Proves the correctness fix (drafts must not leak to parents/students) plus the
bulk publish workflow:
  • report-card shows staff everything, but shows an owner (parent/student) only
    published grades — drafts are hidden
  • publish_grades flips status for a class+term and reports the count
  • publish-status summarises published vs draft
  • publishing refuses a scope with no class or exam (too broad)

...and the approval gate layered on top of it: releasing results to parents needs
the class's ReportApproval to have reached `approved`, the parent card needs it
at `published`, and RETRACTION needs neither — pulling a wrong result back must
never be blocked by workflow state.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Grade, GradeStatus, Student, ParentGuardian, Exam
from app.models.modules.academics import ReportApproval
from app.routers.modules.school import (
    get_report_card, publish_grades, grade_publish_status, create_subject,
)
from app.schemas.grade import GradePublish
from app.schemas.subject import SubjectCreate

pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _approval(db, org, class_id, term="Term 1", stage="approved") -> ReportApproval:
    """The class's report workflow row — the school's sign-off that results for
    this term may go out. `approved` unlocks publishing; `published` is what the
    parent card additionally requires."""
    r = ReportApproval(id=str(uuid.uuid4()), class_id=class_id, term=term,
                       stage=stage, org_id=org.id)
    db.add(r)
    await db.commit()
    return r


async def _two_grades(db, org, teacher, student):
    """One draft + one published grade for the student, Term 1."""
    subj = await create_subject(SubjectCreate(name="Mathematics"), request=None, db=db, current_user=teacher)
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=80,
                 max_score=100, term="Term 1", status=GradeStatus.DRAFT, org_id=org.id))
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=90,
                 max_score=100, term="Term 1", status=GradeStatus.PUBLISHED, org_id=org.id))
    await db.commit()
    return subj


async def test_report_card_staff_sees_drafts(db, org, teacher, school_class, student):
    await _two_grades(db, org, teacher, student)
    staff = await _preset_user(db, org, "teacher")  # holds school:students:read
    card = await get_report_card(student.id, term="Term 1", db=db, current_user=staff)
    assert len(card["grades"]) == 2  # draft + published


async def test_report_card_owner_sees_published_only(db, org, teacher, school_class, student):
    await _two_grades(db, org, teacher, student)
    await _approval(db, org, school_class.id, stage="published")  # term released to parents
    parent = await _preset_user(db, org, "parent")  # no school:students:read
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=student.id, org_id=org.id))
    await db.commit()
    card = await get_report_card(student.id, term="Term 1", db=db, current_user=parent)
    assert len(card["grades"]) == 1
    assert card["grades"][0]["score"] == 90 and card["grades"][0]["status"] == "published"
    assert card["grades"][0]["subject_name"] == "Mathematics"  # readable, not a raw uuid
    assert card["average"] == 90


async def test_publish_flips_status_and_counts(db, org, teacher, school_class, student):
    subj = await create_subject(SubjectCreate(name="English"), request=None, db=db, current_user=teacher)
    g = Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=75,
              max_score=100, term="Term 1", status=GradeStatus.DRAFT, org_id=org.id)
    db.add(g)
    await db.commit()
    # Publishing is gated on the class's sign-off; without this row the call 422s
    # (see test_publish_without_approval_is_refused).
    await _approval(db, org, school_class.id)

    before = await grade_publish_status(term="Term 1", class_id=school_class.id, db=db, current_user=teacher)
    assert before["total"] == 1 and before["draft"] == 1 and before["published"] == 0

    res = await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="published"),
                               request=None, db=db, current_user=teacher)
    assert res["updated"] == 1 and res["status"] == "published"
    await db.refresh(g)
    assert g.status == GradeStatus.PUBLISHED

    after = await grade_publish_status(term="Term 1", class_id=school_class.id, db=db, current_user=teacher)
    assert after["published"] == 1 and after["draft"] == 0

    # unpublish round-trips
    await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="draft"),
                         request=None, db=db, current_user=teacher)
    await db.refresh(g)
    assert g.status == GradeStatus.DRAFT


async def test_publish_refuses_broad_scope(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await publish_grades(GradePublish(term="Term 1", status="published"),
                             request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


# ── Approval gate on publishing ────────────────────────────────────────────────

async def test_publish_without_approval_is_refused(db, org, teacher, school_class, student):
    """No workflow row for the class + term → no release, however ready the
    grades themselves are."""
    subj = await create_subject(SubjectCreate(name="Civics"), request=None, db=db, current_user=teacher)
    g = Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=70,
              max_score=100, term="Term 1", status=GradeStatus.DRAFT, org_id=org.id)
    db.add(g)
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="published"),
                             request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422
    assert "not been approved" in exc.value.detail
    await db.refresh(g)
    assert g.status == GradeStatus.DRAFT  # refused outright, not partially applied


async def test_publish_refused_while_workflow_below_approved(db, org, teacher, school_class, student):
    """A report still in review is not a licence to publish — every stage below
    `approved` is refused."""
    subj = await create_subject(SubjectCreate(name="Music"), request=None, db=db, current_user=teacher)
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=70,
                 max_score=100, term="Term 1", status=GradeStatus.DRAFT, org_id=org.id))
    await db.commit()

    for stage in ("draft", "submitted", "reviewed"):
        r = await _approval(db, org, school_class.id, stage=stage)
        with pytest.raises(HTTPException) as exc:
            await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="published"),
                                 request=None, db=db, current_user=teacher)
        assert exc.value.status_code == 422, f"stage {stage} should not permit publishing"
        await db.delete(r)
        await db.commit()


async def test_publish_allowed_when_already_published(db, org, teacher, school_class, student):
    """Re-publishing after a retraction doesn't demand a stage round-trip."""
    subj = await create_subject(SubjectCreate(name="Art"), request=None, db=db, current_user=teacher)
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=70,
                 max_score=100, term="Term 1", status=GradeStatus.DRAFT, org_id=org.id))
    await db.commit()
    await _approval(db, org, school_class.id, stage="published")

    res = await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="published"),
                               request=None, db=db, current_user=teacher)
    assert res["updated"] == 1
    assert res["workflow_stage"] == "published" and res["parent_visible"] is True
    # Already released — the original stamp is not overwritten by a re-publish.
    assert res["workflow_advanced"] is False


async def test_publish_advances_the_workflow_to_published(db, org, teacher, school_class, student):
    """Releasing the results IS the act `published` records: a successful publish
    carries an approved workflow the last step itself, so there is no state where
    grades are out but the card stays dark."""
    subj = await create_subject(SubjectCreate(name="Drama"), request=None, db=db, current_user=teacher)
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=70,
                 max_score=100, term="Term 1", status=GradeStatus.DRAFT, org_id=org.id))
    await db.commit()
    approval = await _approval(db, org, school_class.id, stage="approved")

    res = await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="published"),
                               request=None, db=db, current_user=teacher)
    assert res["updated"] == 1
    assert res["workflow_stage"] == "published"
    assert res["parent_visible"] is True and res["workflow_advanced"] is True

    await db.refresh(approval)
    assert approval.stage == "published"
    assert approval.published_by == teacher.id and approval.published_at is not None


async def test_auto_advance_makes_the_card_visible_in_one_step(db, org, teacher, school_class, student):
    """The dead zone the auto-advance closes: approve, publish, and the parent can
    see it — no separate trip to the Report Workflow page."""
    await _two_grades(db, org, teacher, student)   # one draft + one published
    parent = await _preset_user(db, org, "parent")
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=student.id, org_id=org.id))
    await db.commit()
    await _approval(db, org, school_class.id, stage="approved")

    assert (await get_report_card(student.id, term="Term 1", db=db, current_user=parent))["grades"] == []

    await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="published"),
                         request=None, db=db, current_user=teacher)
    card = await get_report_card(student.id, term="Term 1", db=db, current_user=parent)
    assert len(card["grades"]) == 2   # both now published, and the class is released


async def test_auto_advance_does_not_fire_on_an_empty_scope(db, org, teacher, school_class):
    """You cannot release nothing: a publish that matches no grades leaves the
    workflow where it was."""
    approval = await _approval(db, org, school_class.id, stage="approved")
    res = await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="published"),
                               request=None, db=db, current_user=teacher)
    assert res["matched"] == 0 and res["workflow_advanced"] is False
    await db.refresh(approval)
    assert approval.stage == "approved"


async def test_retraction_leaves_the_workflow_stage_alone(db, org, teacher, school_class, student):
    """Auto-advance is a publish-only move. Pulling grades back doesn't rewind the
    workflow — that stays a deliberate act on the workflow page."""
    subj = await create_subject(SubjectCreate(name="Latin II"), request=None, db=db, current_user=teacher)
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=70,
                 max_score=100, term="Term 1", status=GradeStatus.PUBLISHED, org_id=org.id))
    await db.commit()
    approval = await _approval(db, org, school_class.id, stage="published")

    res = await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="draft"),
                               request=None, db=db, current_user=teacher)
    assert res["workflow_advanced"] is False
    await db.refresh(approval)
    assert approval.stage == "published"


async def test_retraction_to_draft_needs_no_approval(db, org, teacher, school_class, student):
    """Pulling results back is unrestricted — a wrong result must never sit in
    front of parents waiting on a workflow stage."""
    subj = await create_subject(SubjectCreate(name="Biology"), request=None, db=db, current_user=teacher)
    g = Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=75,
              max_score=100, term="Term 1", status=GradeStatus.PUBLISHED, org_id=org.id)
    db.add(g)
    await db.commit()
    assert (await db.execute(select(ReportApproval))).scalars().first() is None  # no sign-off anywhere

    res = await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="draft"),
                               request=None, db=db, current_user=teacher)
    assert res["updated"] == 1 and res["status"] == "draft"
    await db.refresh(g)
    assert g.status == GradeStatus.DRAFT


async def test_publish_via_exam_resolves_the_class(db, org, teacher, school_class, student):
    """Scope given as an exam: the class comes off the exam, and that class's
    approval is what gets checked."""
    subj = await create_subject(SubjectCreate(name="Chemistry"), request=None, db=db, current_user=teacher)
    exam = Exam(id=str(uuid.uuid4()), name="Mid-term", subject_id=subj["id"],
                class_id=school_class.id, term="Term 1", org_id=org.id)
    db.add(exam)
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], exam_id=exam.id,
                 score=75, max_score=100, term="Term 1", status=GradeStatus.DRAFT, org_id=org.id))
    await db.commit()

    with pytest.raises(HTTPException) as exc:   # class resolved, but unapproved
        await publish_grades(GradePublish(term="Term 1", exam_id=exam.id, status="published"),
                             request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422

    await _approval(db, org, school_class.id)
    res = await publish_grades(GradePublish(term="Term 1", exam_id=exam.id, status="published"),
                               request=None, db=db, current_user=teacher)
    assert res["updated"] == 1


async def test_publish_fails_closed_when_class_cannot_be_resolved(db, org, teacher, student):
    """An exam with no class names nothing to check — refused, rather than
    published on the strength of an approval nobody gave."""
    subj = await create_subject(SubjectCreate(name="Geography"), request=None, db=db, current_user=teacher)
    exam = Exam(id=str(uuid.uuid4()), name="Standalone", subject_id=subj["id"],
                class_id=None, term="Term 1", org_id=org.id)
    db.add(exam)
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await publish_grades(GradePublish(term="Term 1", exam_id=exam.id, status="published"),
                             request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422
    assert "resolve a class" in exc.value.detail


# ── Approval gate on the parent card ───────────────────────────────────────────

async def test_owner_card_hidden_until_workflow_published(db, org, teacher, school_class, student):
    """Published grades alone don't reach a parent: the class's workflow has to
    say `published` too. Staff are unaffected."""
    await _two_grades(db, org, teacher, student)
    parent = await _preset_user(db, org, "parent")
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=student.id, org_id=org.id))
    await db.commit()

    approval = await _approval(db, org, school_class.id, stage="approved")  # signed off, not released
    card = await get_report_card(student.id, term="Term 1", db=db, current_user=parent)
    assert card["grades"] == [] and card["subjects"] == []
    assert card["position"] is None          # standing withheld along with the results

    staff = await _preset_user(db, org, "teacher")
    staff_card = await get_report_card(student.id, term="Term 1", db=db, current_user=staff)
    assert len(staff_card["grades"]) == 2    # gate is owner-only

    approval.stage = "published"
    await db.commit()
    card = await get_report_card(student.id, term="Term 1", db=db, current_user=parent)
    assert len(card["grades"]) == 1 and card["grades"][0]["score"] == 90


async def test_owner_card_gate_is_per_term(db, org, teacher, school_class, student):
    """Releasing Term 1 does not release Term 2."""
    subj = await create_subject(SubjectCreate(name="History"), request=None, db=db, current_user=teacher)
    for term in ("Term 1", "Term 2"):
        db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=80,
                     max_score=100, term=term, status=GradeStatus.PUBLISHED, org_id=org.id))
    await db.commit()
    await _approval(db, org, school_class.id, term="Term 1", stage="published")

    parent = await _preset_user(db, org, "parent")
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=student.id, org_id=org.id))
    await db.commit()

    assert len((await get_report_card(student.id, term="Term 1", db=db, current_user=parent))["grades"]) == 1
    assert (await get_report_card(student.id, term="Term 2", db=db, current_user=parent))["grades"] == []
    # Untermed request: only the released term comes back, not both.
    assert len((await get_report_card(student.id, db=db, current_user=parent))["grades"]) == 1


async def test_owner_card_fails_closed_for_unclassed_student(db, org, teacher, student_user):
    """No class → no workflow row can vouch for the results → nothing shown."""
    loose = Student(id=str(uuid.uuid4()), student_id="S-LOOSE", first_name="No", last_name="Class",
                    email=student_user.email, user_id=student_user.id, class_id=None, org_id=org.id)
    db.add(loose)
    subj = await create_subject(SubjectCreate(name="Latin"), request=None, db=db, current_user=teacher)
    db.add(Grade(id=str(uuid.uuid4()), student_id=loose.id, subject_id=subj["id"], score=80,
                 max_score=100, term="Term 1", status=GradeStatus.PUBLISHED, org_id=org.id))
    await db.commit()

    parent = await _preset_user(db, org, "parent")
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=loose.id, org_id=org.id))
    await db.commit()

    card = await get_report_card(loose.id, term="Term 1", db=db, current_user=parent)
    assert card["grades"] == []


# ── One workflow row per class + term ──────────────────────────────────────────

async def test_duplicate_workflow_rows_are_refused(db, org, school_class):
    """uq_report_approval_class_term. Duplicates would make "the stage" ambiguous:
    the gates read one row, and a stale second could keep releasing a card the
    first one retracted."""
    from sqlalchemy.exc import IntegrityError

    await _approval(db, org, school_class.id, term="Term 1", stage="approved")
    db.add(ReportApproval(id=str(uuid.uuid4()), class_id=school_class.id, term="Term 1",
                          stage="draft", org_id=org.id))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_same_class_may_hold_one_row_per_term(db, org, school_class):
    """The constraint is per term, not per class."""
    await _approval(db, org, school_class.id, term="Term 1")
    await _approval(db, org, school_class.id, term="Term 2")
    rows = (await db.execute(select(ReportApproval))).scalars().all()
    assert len(rows) == 2
