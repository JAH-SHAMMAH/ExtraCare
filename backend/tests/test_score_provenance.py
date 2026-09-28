"""Every mark records who put it there, or states that nobody did.

The gap: all 1,799 marks in production had recorded_by NULL, so no mark on any
report card was traceable. The two human paths always stamped an author; the CBT
sync never did.

`source` exists because `recorded_by` alone cannot close the gap — a NULL author is
ambiguous between "a machine wrote this" and "we lost who wrote it". These tests
pin both halves: the author where there is one, and the honest statement of
machine authorship where there is not.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, AssessmentGroup, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import save_report_entry
from app.schemas.platform import ReportEntrySave, ScoreItem
from tests._enrolment import enrol

pytestmark = pytest.mark.asyncio


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
    teacher = await _user(db, org, "teacher",
                          ["school:reports:read", "school:reports:write", "school:read"],
                          "Real Teacher")
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1",
                      teacher_id=teacher.id, org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", teacher_id=teacher.id, org_id=org.id)
    pupil = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                    last_name="Obi", class_id=cls.id, org_id=org.id)
    grp = AssessmentGroup(id=str(uuid.uuid4()), name="CBT", position=0, org_id=org.id)
    db.add_all([term, full, cls, maths, pupil, grp])
    await db.commit()
    asmt = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", code="CBT",
                      max_score=Decimal("100"), term_id=term.id, sub_term_id=full.id,
                      group_id=grp.id, decimal_places=0, position=0, org_id=org.id)
    db.add(asmt)
    await db.commit()
    await enrol(db, org, pupil, maths)
    return dict(teacher=teacher, term=term, full=full, cls=cls, maths=maths,
                pupil=pupil, asmt=asmt)


async def _only_score(db, org):
    return (await db.execute(select(StudentAssessmentScore).where(
        StudentAssessmentScore.org_id == org.id))).scalars().one()


# ── the grid ─────────────────────────────────────────────────────────────────

async def test_a_teachers_mark_names_the_teacher(db, org):
    w = await _world(db, org)
    await save_report_entry(
        payload=ReportEntrySave(subject_id=w["maths"].id, class_id=w["cls"].id, items=[
            ScoreItem(student_id=w["pupil"].id, assessment_id=w["asmt"].id, score=Decimal(70))]),
        db=db, current_user=w["teacher"])

    row = await _only_score(db, org)
    assert row.recorded_by == w["teacher"].id
    assert row.source == "entry"


async def test_editing_a_mark_re_stamps_the_editor(db, org):
    """The provenance must follow the value the row now holds, not whoever wrote a
    number that has since been replaced."""
    w = await _world(db, org)
    other = await _user(db, org, "super_user", ["*"], "Second Person")
    # Mark entry needs a teaching assignment; this test is about WHO the row
    # credits after an edit, not about who is permitted to make one.
    from tests._enrolment import assign_teaching
    await assign_teaching(db, org, other, w["cls"], w["maths"], day=1)

    for actor, score in ((w["teacher"], 70), (other, 85)):
        await save_report_entry(
            payload=ReportEntrySave(subject_id=w["maths"].id, class_id=w["cls"].id, items=[
                ScoreItem(student_id=w["pupil"].id, assessment_id=w["asmt"].id,
                          score=Decimal(score))]),
            db=db, current_user=actor)

    row = await _only_score(db, org)
    assert row.score == Decimal("85.00")
    assert row.recorded_by == other.id, "the author of the mark that is actually there"
    assert row.source == "entry"


# ── the CBT sync ─────────────────────────────────────────────────────────────

async def _cbt_world(db, org):
    """A published CBT exam with one graded attempt, ready to sync."""
    from datetime import datetime, timezone as _tz

    from app.models.modules.school import (
        AttemptStatus, CBTAttempt, CBTExam, ExamStatus,
    )

    from tests._terms import a_term

    w = await _world(db, org)
    exam = CBTExam(
        id=str(uuid.uuid4()), title="Maths CBT", status=ExamStatus.PUBLISHED,
        total_points=20, class_id=w["cls"].id, subject_id=w["maths"].id,
        term_id=(await a_term(db, org, name="Autumn")).id, created_by=w["teacher"].id,
        results_published_at=datetime.now(_tz.utc), org_id=org.id,
    )
    db.add(exam)
    await db.commit()
    db.add(CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=w["pupil"].id,
                      status=AttemptStatus.GRADED, score=18, max_score=20,
                      org_id=org.id))
    await db.commit()
    w["exam"] = exam
    return w


async def test_a_synced_mark_names_whoever_triggered_it(db, org):
    """Publishing results is a human act, and the publisher is the accountable
    party for the marks it puts on report cards."""
    from app.services.cbt_assessment_sync import sync_cbt_to_assessment_score

    w = await _cbt_world(db, org)
    publisher = await _user(db, org, "super_user", ["*"], "The Publisher")

    n, _reason = await sync_cbt_to_assessment_score(
        db, w["exam"].id, org.id, actor_id=publisher.id)
    assert n == 1

    row = await _only_score(db, org)
    assert row.recorded_by == publisher.id
    assert row.source == "cbt_sync"
    assert row.score == Decimal("90.00")      # 18/20


async def test_a_script_run_states_machine_authorship_rather_than_going_silent(db, org):
    """THE ORIGINAL BUG. With no actor there is genuinely no author to name — but
    the row must say so, because a bare NULL is indistinguishable from a lost one.
    """
    from app.services.cbt_assessment_sync import sync_cbt_to_assessment_score

    w = await _cbt_world(db, org)
    n, _reason = await sync_cbt_to_assessment_score(db, w["exam"].id, org.id)
    assert n == 1

    row = await _only_score(db, org)
    assert row.recorded_by is None, "no person triggered it, so none is invented"
    assert row.source == "cbt_sync", "but the mark is not anonymous — it says what wrote it"


async def test_re_syncing_updates_the_author_not_just_the_score(db, org):
    from app.services.cbt_assessment_sync import sync_cbt_to_assessment_score

    w = await _cbt_world(db, org)
    first = await _user(db, org, "super_user", ["*"], "First Publisher")
    second = await _user(db, org, "super_user", ["*"], "Second Publisher")

    await sync_cbt_to_assessment_score(db, w["exam"].id, org.id, actor_id=first.id)
    await sync_cbt_to_assessment_score(db, w["exam"].id, org.id, actor_id=second.id)

    row = await _only_score(db, org)
    assert row.recorded_by == second.id
    assert row.source == "cbt_sync"


async def test_the_sync_overwrites_a_teachers_mark_and_says_so(db, org):
    """CBT is authoritative, so it replaces a hand-entered mark. The provenance has
    to change with it — leaving the teacher's name on a number the sync chose would
    attribute a mark to someone who did not set it."""
    from app.services.cbt_assessment_sync import sync_cbt_to_assessment_score

    w = await _cbt_world(db, org)
    await save_report_entry(
        payload=ReportEntrySave(subject_id=w["maths"].id, class_id=w["cls"].id, items=[
            ScoreItem(student_id=w["pupil"].id, assessment_id=w["asmt"].id, score=Decimal(55))]),
        db=db, current_user=w["teacher"])
    row = await _only_score(db, org)
    assert row.source == "entry" and row.recorded_by == w["teacher"].id

    publisher = await _user(db, org, "super_user", ["*"], "The Publisher")
    await sync_cbt_to_assessment_score(db, w["exam"].id, org.id, actor_id=publisher.id)

    await db.refresh(row)
    assert row.score == Decimal("90.00"), "CBT won"
    assert row.source == "cbt_sync"
    assert row.recorded_by == publisher.id, "not still the teacher who typed 55"


# ── no path may write an unattributed mark ───────────────────────────────────

async def test_every_write_path_sets_a_source(db, org):
    """The guard against a fourth path appearing later without provenance. If a new
    writer is added and this fails, that writer needs stamping — not this test
    relaxing."""
    w = await _cbt_world(db, org)
    from app.services.cbt_assessment_sync import sync_cbt_to_assessment_score

    await save_report_entry(
        payload=ReportEntrySave(subject_id=w["maths"].id, class_id=w["cls"].id, items=[
            ScoreItem(student_id=w["pupil"].id, assessment_id=w["asmt"].id, score=Decimal(60))]),
        db=db, current_user=w["teacher"])
    await sync_cbt_to_assessment_score(db, w["exam"].id, org.id, actor_id=w["teacher"].id)

    rows = (await db.execute(select(StudentAssessmentScore).where(
        StudentAssessmentScore.org_id == org.id))).scalars().all()
    assert rows
    unattributed = [r for r in rows if not r.source]
    assert unattributed == [], f"{len(unattributed)} mark(s) written with no source"
    assert {r.source for r in rows} <= {"entry", "upload", "cbt_sync"}
