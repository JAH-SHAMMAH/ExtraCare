"""A skipped CBT->Make Report sync has to say so, to someone who can act on it.

The sync has always known why it skipped — `sync_cbt_to_assessment_score` has
returned `(rows, reason)` from the start, and the publish endpoint has always put
that reason in its response. Nothing ever displayed it. The teacher who opened
Make Report saw a blank "CBT Exam Score" column, indistinguishable from a class
nobody had marked, and the only recovery was to unpublish and republish the exam
— which yanks scores away from students to fix something unrelated to them.

Three things are pinned here:

  1. WHO CAN ACT decides what is shown. Three of the reasons describe the school's
     academic setup (no matching AcademicTerm, no sub-term at all, no Assessment
     creatable from them). A teacher holds neither the scope nor the context for
     those, so they get ADMIN_FIX_NOTICE while admins get the precise text. The
     reasons a teacher CAN act on are shown verbatim to everyone — generalising
     those would be a regression, so that is asserted too.

  2. ONE SOURCE OF TRUTH. The results panel, the Make Report notice and the sync
     all call `assessment_block_reason`. If they could drift, the teacher would be
     shown a reason the sync did not act on.

  3. THE REASON OUTLIVES THE TOAST. A publish blocked by setup leaves an audit
     record carrying the PRECISE text, because the person publishing may be a
     teacher who cannot use it and the toast is gone on the next navigation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.modules.academics import ReportApproval
from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, StudentAssessmentScore,
)
from app.models.modules.school import (
    AttemptStatus, CBTAttempt, CBTExam, ExamStatus, SchoolClass, Student, Subject,
)
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.cbt import (
    exam_results, publish_exam_results, sync_exam_to_assessment,
)
from app.services.cbt_assessment_sync import (
    ADMIN_FIX_NOTICE, SyncBlock, assessment_block_reason,
    sync_cbt_to_assessment_score,
)

TERM_NAME = "Term 1"


# ── fixtures ──────────────────────────────────────────────────────────────────

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


async def _school(db, org, *, with_term=True, with_sub_term=True):
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    rows = [cls, subj]
    term = sub = None
    if with_term:
        term = AcademicTerm(id=str(uuid.uuid4()), name=TERM_NAME, org_id=org.id)
        rows.append(term)
    if with_sub_term:
        sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
        rows.append(sub)
    db.add_all(rows)
    await db.commit()
    return cls, subj, term, sub


async def _exam(db, org, cls, subj, *, published=True, term=TERM_NAME, subject=True):
    e = CBTExam(
        id=str(uuid.uuid4()), title="Maths CBT", status=ExamStatus.PUBLISHED,
        total_points=10, class_id=cls.id, org_id=org.id, term=term,
        subject_id=subj.id if subject else None,
        results_published_at=datetime.now(timezone.utc) if published else None,
        created_by=(await _user(db, org, "org_admin")).id,
    )
    db.add(e)
    await db.commit()
    return e


# ── 1. who can act decides what is shown ──────────────────────────────────────

def test_a_teacher_fixable_reason_is_shown_verbatim_to_everyone():
    """Generalising these would be the regression: "Exam has no subject assigned"
    is precisely what the teacher needs, and they can go and fix it."""
    b = SyncBlock("Exam has no subject assigned")
    assert b.admin_only is False
    assert b.message_for(is_admin=False) == "Exam has no subject assigned"
    assert b.message_for(is_admin=True) == "Exam has no subject assigned"


def test_a_setup_reason_is_generalised_for_teachers_but_not_for_admins():
    b = SyncBlock("No academic term named 'Term 1' exists", admin_only=True)
    assert b.message_for(is_admin=False) == ADMIN_FIX_NOTICE
    assert b.message_for(is_admin=True) == "No academic term named 'Term 1' exists"
    # The teacher's version must not leak the jargon it replaces.
    assert "AcademicTerm" not in ADMIN_FIX_NOTICE
    assert "sub-term" not in ADMIN_FIX_NOTICE.lower()


def test_the_block_is_still_an_ordinary_string():
    """Existing callers pass it to f-strings, `in` tests and JSON untouched. If
    this stops holding, two backfill scripts and the publish response break."""
    b = SyncBlock("frozen scores", admin_only=True)
    assert isinstance(b, str)
    assert "frozen" in b and f"{b}" == "frozen scores"
    import json
    assert json.dumps({"reason": b}) == '{"reason": "frozen scores"}'


# ── 2. the real blocks, classified correctly ──────────────────────────────────

@pytest.mark.asyncio
async def test_missing_academic_term_is_admin_only(db, org):
    """The exam is perfect; the school simply has no term by that name. Nothing a
    teacher can do — and the likeliest cause is a spelling drift they cannot see."""
    cls, subj, _, _ = await _school(db, org, with_term=False)
    exam = await _exam(db, org, cls, subj)

    block = await assessment_block_reason(db, exam, org.id)
    assert block is not None and block.admin_only is True
    assert TERM_NAME in block.reason
    assert block.message_for(is_admin=False) == ADMIN_FIX_NOTICE


@pytest.mark.asyncio
async def test_missing_sub_term_is_admin_only(db, org):
    cls, subj, _, _ = await _school(db, org, with_sub_term=False)
    exam = await _exam(db, org, cls, subj)

    block = await assessment_block_reason(db, exam, org.id)
    assert block is not None and block.admin_only is True
    assert "sub-term" in block.reason.lower()


@pytest.mark.asyncio
async def test_an_untagged_exam_is_the_teachers_to_fix(db, org):
    cls, subj, _, _ = await _school(db, org)
    exam = await _exam(db, org, cls, subj, subject=False)

    block = await assessment_block_reason(db, exam, org.id)
    assert block is not None and block.admin_only is False
    assert block.message_for(is_admin=False) == block.reason


@pytest.mark.asyncio
async def test_a_frozen_report_is_explained_not_generalised(db, org):
    """A teacher cannot retract the report, but "your class's report is already
    published" is the context they need and names the page to ask about. Hiding
    that behind a generic notice would make it less useful, not safer."""
    cls, subj, _, _ = await _school(db, org)
    db.add(ReportApproval(id=str(uuid.uuid4()), class_id=cls.id, term=TERM_NAME,
                          stage="published", org_id=org.id))
    await db.commit()
    exam = await _exam(db, org, cls, subj)

    block = await assessment_block_reason(db, exam, org.id)
    assert block is not None and block.admin_only is False
    assert "frozen" in block.reason
    assert block.message_for(is_admin=False) == block.reason


@pytest.mark.asyncio
async def test_a_clean_exam_reports_no_block(db, org):
    cls, subj, _, _ = await _school(db, org)
    exam = await _exam(db, org, cls, subj)
    assert await assessment_block_reason(db, exam, org.id) is None


@pytest.mark.asyncio
async def test_the_status_helper_writes_nothing(db, org):
    """It backs a read endpoint and a grid load. Creating an Assessment as a side
    effect of *looking* would mean merely opening Make Report mutated the term."""
    cls, subj, term, sub = await _school(db, org)
    exam = await _exam(db, org, cls, subj)
    before = len((await db.execute(select(Assessment))).scalars().all())

    await assessment_block_reason(db, exam, org.id)
    await assessment_block_reason(db, exam, org.id)

    assert len((await db.execute(select(Assessment))).scalars().all()) == before


# ── 3. one source of truth ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_sync_returns_exactly_what_the_status_helper_reports(db, org):
    """If these could differ, the teacher would be shown a reason the sync did not
    act on. The sync delegates, so they cannot."""
    cls, subj, _, _ = await _school(db, org, with_term=False)
    exam = await _exam(db, org, cls, subj)

    block = await assessment_block_reason(db, exam, org.id)
    rows, reason = await sync_cbt_to_assessment_score(db, exam.id, org.id)

    assert rows == 0
    assert reason == block
    assert getattr(reason, "admin_only", None) is True


# ── 4. the reason outlives the toast ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_publishing_into_a_setup_problem_leaves_an_audit_record(db, org):
    """The publisher may be a teacher who can do nothing with the reason, and the
    toast dies on the next click. An administrator must still be able to find it."""
    cls, subj, _, _ = await _school(db, org, with_term=False)
    exam = await _exam(db, org, cls, subj, published=False)
    teacher = await _user(db, org, "teacher")

    body = (await publish_exam_results(
        exam.id, request=None, db=db, current_user=teacher))["assessment"]
    assert body["synced"] == 0
    # The teacher is handed the generic notice...
    assert body["reason"] == ADMIN_FIX_NOTICE

    # ...while the precise text survives in the audit log.
    labels = [
        a.resource_label or ""
        for a in (await db.execute(
            select(AuditLog).where(AuditLog.resource_type == "StudentAssessmentScore")
        )).scalars().all()
    ]
    assert any(TERM_NAME in x and "administrator" in x for x in labels), labels


@pytest.mark.asyncio
async def test_an_admin_publishing_sees_the_precise_reason(db, org):
    cls, subj, _, _ = await _school(db, org, with_term=False)
    exam = await _exam(db, org, cls, subj, published=False)
    admin = await _user(db, org, "org_admin")

    reason = (await publish_exam_results(
        exam.id, request=None, db=db, current_user=admin))["assessment"]["reason"]
    assert reason != ADMIN_FIX_NOTICE and TERM_NAME in reason


# ── 5. the retry path ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_sync_can_be_rerun_without_unpublishing(db, org):
    """The point of the endpoint: fix the setup, re-run, and students never lose
    sight of their results in the process."""
    cls, subj, _, _ = await _school(db, org, with_term=False)
    exam = await _exam(db, org, cls, subj)
    stu = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="A", last_name="B",
                  class_id=cls.id, org_id=org.id)
    db.add(stu)
    await db.commit()
    db.add(CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=stu.id,
                      status=AttemptStatus.GRADED, score=8, max_score=10, org_id=org.id))
    await db.commit()
    admin = await _user(db, org, "org_admin")

    # Blocked: the term does not exist yet.
    r = await sync_exam_to_assessment(exam.id, request=None, db=db, current_user=admin)
    assert r["synced"] == 0 and r["admin_only"] is True
    assert (await db.execute(select(StudentAssessmentScore))).scalars().first() is None

    # An admin adds the missing term. (The sub-term already exists; there is a
    # unique index on (org_id, name), so a second "Full-Term" is a real error.)
    db.add(AcademicTerm(id=str(uuid.uuid4()), name=TERM_NAME, org_id=org.id))
    await db.commit()

    # ...and the same button now lands the scores, with no unpublish in between.
    r = await sync_exam_to_assessment(exam.id, request=None, db=db, current_user=admin)
    assert r["synced"] == 1 and r["reason"] is None
    assert exam.results_published_at is not None  # students never lost access

    score = (await db.execute(select(StudentAssessmentScore))).scalars().one()
    assert float(score.score) == 80.0


@pytest.mark.asyncio
async def test_rerunning_the_sync_is_idempotent(db, org):
    cls, subj, _, _ = await _school(db, org)
    exam = await _exam(db, org, cls, subj)
    stu = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="A", last_name="B",
                  class_id=cls.id, org_id=org.id)
    db.add(stu)
    await db.commit()
    db.add(CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=stu.id,
                      status=AttemptStatus.GRADED, score=7, max_score=10, org_id=org.id))
    await db.commit()
    admin = await _user(db, org, "org_admin")

    await sync_exam_to_assessment(exam.id, request=None, db=db, current_user=admin)
    await sync_exam_to_assessment(exam.id, request=None, db=db, current_user=admin)

    rows = (await db.execute(select(StudentAssessmentScore))).scalars().all()
    assert len(rows) == 1, "re-running must update in place, never duplicate"


# ── 6. the status panel ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_results_endpoint_reports_the_assessment_feed(db, org):
    """Previously the response described the gradebook feed only, so a skipped
    assessment sync was invisible on the page that publishes it."""
    cls, subj, _, _ = await _school(db, org, with_term=False)
    exam = await _exam(db, org, cls, subj)
    admin = await _user(db, org, "org_admin")

    a = (await exam_results(exam.id, db=db, current_user=admin))["assessment"]
    assert a["admin_only"] is True
    assert TERM_NAME in a["block_reason"]
    assert a["synced_count"] == 0


@pytest.mark.asyncio
async def test_the_results_endpoint_generalises_for_a_teacher(db, org):
    cls, subj, _, _ = await _school(db, org, with_term=False)
    exam = await _exam(db, org, cls, subj)
    teacher = await _user(db, org, "teacher")

    a = (await exam_results(exam.id, db=db, current_user=teacher))["assessment"]
    assert a["block_reason"] == ADMIN_FIX_NOTICE


# ── 7. the notice where the teacher actually is ───────────────────────────────

@pytest.mark.asyncio
async def test_the_make_report_grid_explains_an_empty_cbt_column(db, org):
    """The whole point of the arc. The grid previously returned assessments,
    students and scores and nothing else, so a skipped sync was indistinguishable
    from a class nobody had marked.

    A frozen report is the case used here because it is the one that actually
    loses marks silently: the teacher publishes CBT results, the scores are
    refused because the class report is already out, and nothing anywhere says so.
    """
    from app.routers.modules.platform import report_entry_grid

    cls, subj, term, _ = await _school(db, org)
    db.add(ReportApproval(id=str(uuid.uuid4()), class_id=cls.id, term=TERM_NAME,
                          stage="published", org_id=org.id))
    await db.commit()
    exam = await _exam(db, org, cls, subj)

    admin = await _user(db, org, "org_admin")
    grid = await report_entry_grid(
        class_id=cls.id, subject_id=subj.id, term_id=term.id,
        db=db, current_user=admin,
    )
    assert grid.notices, "a blocked exam must be explained on the grid"
    assert exam.title in grid.notices[0] and "frozen" in grid.notices[0]


@pytest.mark.asyncio
async def test_the_grid_notice_respects_the_viewers_audience(db, org):
    from app.routers.modules.platform import report_entry_grid

    cls, subj, _, _ = await _school(db, org, with_sub_term=False)
    term = (await db.execute(select(AcademicTerm))).scalars().one()
    exam = await _exam(db, org, cls, subj)
    teacher = await _user(db, org, "teacher")
    admin = await _user(db, org, "org_admin")
    # Make the teacher a real subject teacher, or the grid refuses them outright
    # and the audience split would never be exercised.
    subj.teacher_id = teacher.id
    await db.commit()

    async def notices(user):
        g = await report_entry_grid(class_id=cls.id, subject_id=subj.id,
                                    term_id=term.id, db=db, current_user=user)
        return g.notices

    # The admin is told which setting is missing...
    assert any("sub-term" in n.lower() for n in await notices(admin))
    # ...the teacher is told it is not theirs to fix.
    teacher_notices = await notices(teacher)
    assert teacher_notices and all(ADMIN_FIX_NOTICE in n for n in teacher_notices)


@pytest.mark.asyncio
async def test_a_healthy_grid_carries_no_notices(db, org):
    """Notices must be exceptional. A banner on every load is one nobody reads."""
    from app.routers.modules.platform import report_entry_grid

    cls, subj, term, _ = await _school(db, org)
    await _exam(db, org, cls, subj)
    admin = await _user(db, org, "org_admin")

    grid = await report_entry_grid(class_id=cls.id, subject_id=subj.id,
                                   term_id=term.id, db=db, current_user=admin)
    assert grid.notices == []
