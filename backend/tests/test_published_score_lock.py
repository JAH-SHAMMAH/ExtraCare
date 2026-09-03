"""A published report freezes the marks behind it.

`ReportApproval.stage == "published"` means the school released that class's term
to parents. Editing the scores afterwards changes what a parent already read,
with no re-approval and no trace — so the write paths refuse.

Two paths, two behaviours, deliberately:

  Report Entry (a person typing marks)  -> 422, refuse outright.
  CBT auto-sync (a hook, mid-publish)   -> skip with a reason, do not raise.

The second is the interesting one. `sync_cbt_to_assessment_score` runs inside
`publish_exam_results`; raising there would fail a legitimate CBT publish — and
block releasing results to STUDENTS — over a report-workflow state that has
nothing to do with CBT. It already returns (rows, reason) for every other refusal,
so the freeze uses the same contract.

The freeze reads the CURRENT stage, so retracting the workflow unfreezes editing
again. That round trip is asserted here, because it is the property that makes
the lock usable rather than a trap.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.modules.academics import ReportApproval
from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import save_report_entry
from app.schemas.platform import ReportEntrySave, ScoreItem
from sqlalchemy import select

TERM_NAME = "Term 1"


async def _fixture(db, org, *, stage: str | None = None):
    """A class, a pupil, a subject, an assessment in Term 1 — plus an optional
    ReportApproval at `stage`."""
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name=TERM_NAME, org_id=org.id)
    sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
    db.add_all([cls, subj, term, sub])
    await db.commit()

    stu = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="A", last_name="B",
                  class_id=cls.id, org_id=org.id)
    a = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=100, term_id=term.id,
                   sub_term_id=sub.id, org_id=org.id)
    db.add_all([stu, a])
    if stage:
        db.add(ReportApproval(id=str(uuid.uuid4()), class_id=cls.id, term=TERM_NAME,
                              stage=stage, org_id=org.id))
    await db.commit()
    return cls, stu, subj, a


async def _admin(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="admin", slug=f"a-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Admin", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _save(db, user, cls, subj, a, stu, score=70):
    return await save_report_entry(
        ReportEntrySave(subject_id=subj.id, class_id=cls.id,
                        items=[ScoreItem(student_id=stu.id, assessment_id=a.id, score=score)]),
        db=db, current_user=user,
    )


# ── Report Entry ──────────────────────────────────────────────────────────────

async def test_saving_is_refused_once_the_report_is_published(db, org):
    cls, stu, subj, a = await _fixture(db, org, stage="published")
    user = await _admin(db, org)

    with pytest.raises(HTTPException) as exc:
        await _save(db, user, cls, subj, a, stu)
    assert exc.value.status_code == 422
    assert "frozen" in exc.value.detail
    assert "Retract" in exc.value.detail
    assert TERM_NAME in exc.value.detail
    assert "JSS1 A" in exc.value.detail          # names the class, not just "a class"

    assert (await db.execute(select(StudentAssessmentScore))).scalars().first() is None


@pytest.mark.parametrize("stage", ["draft", "submitted", "reviewed", "approved"])
async def test_saving_is_allowed_at_every_stage_below_published(db, org, stage):
    """Only `published` freezes. Approval alone must not stop a correction."""
    cls, stu, subj, a = await _fixture(db, org, stage=stage)
    user = await _admin(db, org)
    out = await _save(db, user, cls, subj, a, stu)
    assert out["saved"] == 1


async def test_saving_is_allowed_with_no_workflow_row_at_all(db, org):
    """Classes with no workflow row are not retroactively frozen."""
    cls, stu, subj, a = await _fixture(db, org, stage=None)
    user = await _admin(db, org)
    assert (await _save(db, user, cls, subj, a, stu))["saved"] == 1


async def test_retracting_unfreezes_editing(db, org):
    """The property that makes this a lock rather than a trap."""
    cls, stu, subj, a = await _fixture(db, org, stage="published")
    user = await _admin(db, org)

    with pytest.raises(HTTPException):
        await _save(db, user, cls, subj, a, stu)

    approval = (await db.execute(select(ReportApproval))).scalar_one()
    approval.stage = "approved"                  # backward moves are unrestricted
    await db.commit()

    assert (await _save(db, user, cls, subj, a, stu, score=88))["saved"] == 1
    row = (await db.execute(select(StudentAssessmentScore))).scalar_one()
    assert row.score == 88


async def test_a_different_term_is_not_frozen(db, org):
    """The freeze is per (class, term) — publishing Term 1 must not lock Term 2."""
    cls, stu, subj, a = await _fixture(db, org, stage="published")
    user = await _admin(db, org)

    t2 = AcademicTerm(id=str(uuid.uuid4()), name="Term 2", org_id=org.id)
    db.add(t2)
    await db.commit()
    sub_id = (await db.execute(select(AcademicSubTerm.id))).scalars().first()
    a2 = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=100, term_id=t2.id,
                    sub_term_id=sub_id, org_id=org.id)
    db.add(a2)
    await db.commit()

    assert (await _save(db, user, cls, subj, a2, stu))["saved"] == 1


async def test_a_different_class_is_not_frozen(db, org):
    cls, stu, subj, a = await _fixture(db, org, stage="published")
    user = await _admin(db, org)

    other = SchoolClass(id=str(uuid.uuid4()), name="JSS1 B", level="Secondary", org_id=org.id)
    db.add(other)
    await db.commit()
    stu2 = Student(id=str(uuid.uuid4()), student_id="S-2", first_name="C", last_name="D",
                   class_id=other.id, org_id=org.id)
    db.add(stu2)
    await db.commit()

    assert (await _save(db, user, other, subj, a, stu2))["saved"] == 1


async def test_omitting_class_id_does_not_bypass_the_freeze(db, org):
    """class_id is optional for an admin, so the class is resolved from the pupils
    when it is absent — otherwise leaving it out would be a way around the lock."""
    cls, stu, subj, a = await _fixture(db, org, stage="published")
    user = await _admin(db, org)

    with pytest.raises(HTTPException) as exc:
        await save_report_entry(
            ReportEntrySave(subject_id=subj.id, class_id=None,
                            items=[ScoreItem(student_id=stu.id, assessment_id=a.id, score=55)]),
            db=db, current_user=user,
        )
    assert exc.value.status_code == 422
    assert "frozen" in exc.value.detail


# ── CBT auto-sync ─────────────────────────────────────────────────────────────

async def test_cbt_sync_skips_a_frozen_class_without_raising(db, org):
    """It must not raise: this runs inside publish_exam_results, and failing there
    would block releasing results to students over an unrelated workflow state."""
    from app.models.modules.school import CBTExam, ExamStatus
    from app.services.cbt_assessment_sync import sync_cbt_to_assessment_score

    cls, stu, subj, a = await _fixture(db, org, stage="published")
    exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", status=ExamStatus.PUBLISHED,
                   total_points=10, subject_id=subj.id, class_id=cls.id, term=TERM_NAME,
                   results_published_at=__import__("datetime").datetime.now(
                       __import__("datetime").timezone.utc),
                   created_by=(await _admin(db, org)).id, org_id=org.id)
    db.add(exam)
    await db.commit()

    rows, reason = await sync_cbt_to_assessment_score(db, exam.id, org.id)
    assert rows == 0
    assert reason is not None and "frozen" in reason
    assert (await db.execute(select(StudentAssessmentScore))).scalars().first() is None


async def test_cbt_sync_proceeds_when_the_report_is_not_published(db, org):
    """The freeze must not become a blanket block on the CBT feed."""
    from app.models.modules.school import CBTExam, ExamStatus
    from app.services.cbt_assessment_sync import sync_cbt_to_assessment_score

    cls, stu, subj, a = await _fixture(db, org, stage="approved")
    exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", status=ExamStatus.PUBLISHED,
                   total_points=10, subject_id=subj.id, class_id=cls.id, term=TERM_NAME,
                   results_published_at=__import__("datetime").datetime.now(
                       __import__("datetime").timezone.utc),
                   created_by=(await _admin(db, org)).id, org_id=org.id)
    db.add(exam)
    await db.commit()

    rows, reason = await sync_cbt_to_assessment_score(db, exam.id, org.id)
    # Whatever it does next (no attempts here), it must NOT be the freeze refusing.
    assert reason is None or "frozen" not in reason
