"""CBT gradebook feed (Phase 2): published CBT results feed DRAFT Grade rows.

Option I: a held-and-unpublished exam feeds nothing; publishing releases results
to students AND (when the exam is fully tagged) auto-feeds the gradebook as DRAFT
grades; unpublishing redrafts them. Grades are normalised to a percentage /100 so
CBT marks sit comparably beside manual exams. Staff then release them to parents
via the gradebook's own publish step — proven end-to-end by the report-card test.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, func

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import (
    CBTExam, CBTAttempt, CBTAnswer, Subject, Student, Grade, GradeStatus,
    ExamStatus, AttemptStatus,
)
from app.routers.modules.cbt import (
    publish_exam_results, unpublish_exam_results, feed_gradebook, exam_results,
)
from app.routers.modules.school import get_report_card

pytestmark = pytest.mark.asyncio


async def _staff(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"staff-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Staff", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="manager", slug=f"m-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["manager"]), org_id=org.id, is_system=False)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _linked_student(db, org, class_id=None):
    email = f"stu-{uuid.uuid4().hex[:6]}@example.com"
    stu = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
                  first_name="S", last_name="X", email=email, class_id=class_id, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="student", slug=f"student-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=email, full_name="S X", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([stu, role, u])
    await db.commit()
    return stu, u


async def _subject(db, org) -> Subject:
    s = Subject(id=str(uuid.uuid4()), name=f"Maths-{uuid.uuid4().hex[:4]}", org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _exam(db, org, staff, *, hold_results=False, subject_id=None, term=None) -> CBTExam:
    exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", created_by=staff.id, org_id=org.id,
                   status=ExamStatus.PUBLISHED, total_points=20,
                   hold_results=hold_results, subject_id=subject_id, term=term)
    db.add(exam)
    await db.commit()
    return exam


async def _attempt(db, org, exam, student_id, *, score, max_score=20,
                   status=AttemptStatus.GRADED, superseded=False) -> CBTAttempt:
    att = CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=student_id,
                     max_score=max_score, score=score, status=status,
                     started_at=datetime.now(timezone.utc), org_id=org.id,
                     superseded_at=datetime.now(timezone.utc) if superseded else None)
    db.add(att)
    await db.commit()
    return att


async def _grades_for(db, org, exam) -> list[Grade]:
    return (await db.execute(
        select(Grade).where(Grade.cbt_exam_id == exam.id, Grade.org_id == org.id)
    )).scalars().all()


# ── The feed: best attempt, normalisation, DRAFT ──────────────────────────────────

async def test_feed_creates_draft_grade_from_best_attempt(db, org):
    staff = await _staff(db, org)
    stu, _ = await _linked_student(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, subject_id=subj.id, term="Term 1")
    await _attempt(db, org, exam, stu.id, score=12)   # 60% → B
    await _attempt(db, org, exam, stu.id, score=15)   # 75% → A (best)

    res = await feed_gradebook(exam.id, request=None, db=db, current_user=staff)
    assert res["fed"] == 1
    grades = await _grades_for(db, org, exam)
    assert len(grades) == 1
    g = grades[0]
    assert g.student_id == stu.id and g.subject_id == subj.id and g.term == "Term 1"
    assert g.status == GradeStatus.DRAFT
    assert g.score == 75 and g.max_score == 100 and g.grade_letter == "A"  # best, normalised


async def test_feed_excludes_superseded_and_ungraded(db, org):
    staff = await _staff(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, subject_id=subj.id, term="Term 1")
    graded_stu, _ = await _linked_student(db, org)
    superseded_stu, _ = await _linked_student(db, org)
    submitted_stu, _ = await _linked_student(db, org)
    await _attempt(db, org, exam, graded_stu.id, score=16)                       # GRADED active → in
    await _attempt(db, org, exam, superseded_stu.id, score=18, superseded=True)  # superseded → out
    await _attempt(db, org, exam, submitted_stu.id, score=None, status=AttemptStatus.SUBMITTED)  # ungraded → out

    res = await feed_gradebook(exam.id, request=None, db=db, current_user=staff)
    assert res["fed"] == 1
    grades = await _grades_for(db, org, exam)
    assert {g.student_id for g in grades} == {graded_stu.id}


async def test_feed_idempotent_updates_in_place(db, org):
    staff = await _staff(db, org)
    stu, _ = await _linked_student(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, subject_id=subj.id, term="Term 1")
    att = await _attempt(db, org, exam, stu.id, score=14)  # 70% → A

    await feed_gradebook(exam.id, request=None, db=db, current_user=staff)
    g = (await _grades_for(db, org, exam))[0]
    # a teacher promotes it to the parent-facing state, then re-grades higher
    g.status = GradeStatus.PUBLISHED
    att.score = 18  # 90%
    await db.commit()

    res = await feed_gradebook(exam.id, request=None, db=db, current_user=staff)
    assert res["fed"] == 1
    grades = await _grades_for(db, org, exam)
    assert len(grades) == 1  # updated in place, not duplicated
    assert grades[0].score == 90
    assert grades[0].status == GradeStatus.PUBLISHED  # re-sync leaves publish status untouched


# ── Gates: Option I + subject + term ──────────────────────────────────────────────

async def test_held_unpublished_feed_blocked(db, org):
    staff = await _staff(db, org)
    stu, _ = await _linked_student(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, hold_results=True, subject_id=subj.id, term="Term 1")
    await _attempt(db, org, exam, stu.id, score=15)

    with pytest.raises(Exception) as ei:
        await feed_gradebook(exam.id, request=None, db=db, current_user=staff)
    assert getattr(ei.value, "status_code", None) == 422 and "Publish results" in ei.value.detail
    assert await _grades_for(db, org, exam) == []


async def test_feed_requires_subject(db, org):
    staff = await _staff(db, org)
    exam = await _exam(db, org, staff, subject_id=None, term="Term 1")
    with pytest.raises(Exception) as ei:
        await feed_gradebook(exam.id, request=None, db=db, current_user=staff)
    assert getattr(ei.value, "status_code", None) == 422 and "subject" in ei.value.detail.lower()


async def test_feed_requires_term(db, org):
    staff = await _staff(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, subject_id=subj.id, term=None)
    with pytest.raises(Exception) as ei:
        await feed_gradebook(exam.id, request=None, db=db, current_user=staff)
    assert getattr(ei.value, "status_code", None) == 422 and "term" in ei.value.detail.lower()


# ── Publish auto-feed + student release decoupling ───────────────────────────────

async def test_publish_autofeeds_when_tagged(db, org):
    staff = await _staff(db, org)
    stu, _ = await _linked_student(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, hold_results=True, subject_id=subj.id, term="Term 1")
    await _attempt(db, org, exam, stu.id, score=15)

    res = await publish_exam_results(exam.id, request=None, db=db, current_user=staff)
    assert res["gradebook"] == {"fed": 1, "blocked": None}
    grades = await _grades_for(db, org, exam)
    assert len(grades) == 1 and grades[0].status == GradeStatus.DRAFT


async def test_publish_without_subject_still_releases_but_skips_feed(db, org):
    # B(a): a subjectless exam still publishes results to students; only the feed
    # is withheld (loudly reported), never a silent skip that hides the gap.
    staff = await _staff(db, org)
    stu, _ = await _linked_student(db, org)
    exam = await _exam(db, org, staff, hold_results=True, subject_id=None, term="Term 1")
    await _attempt(db, org, exam, stu.id, score=15)

    res = await publish_exam_results(exam.id, request=None, db=db, current_user=staff)
    assert res["published"] is True                       # student release works
    assert res["gradebook"]["fed"] == 0
    assert "subject" in res["gradebook"]["blocked"].lower()  # reported, not silent
    assert await _grades_for(db, org, exam) == []


async def test_unpublish_redrafts_fed_grades(db, org):
    staff = await _staff(db, org)
    stu, _ = await _linked_student(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, hold_results=True, subject_id=subj.id, term="Term 1")
    await _attempt(db, org, exam, stu.id, score=15)

    await publish_exam_results(exam.id, request=None, db=db, current_user=staff)
    g = (await _grades_for(db, org, exam))[0]
    g.status = GradeStatus.PUBLISHED  # staff had released it to parents
    await db.commit()

    res = await unpublish_exam_results(exam.id, request=None, db=db, current_user=staff)
    assert res["grades_redrafted"] == 1
    assert (await _grades_for(db, org, exam))[0].status == GradeStatus.DRAFT  # kept, redrafted


async def test_not_held_exam_feeds_directly(db, org):
    staff = await _staff(db, org)
    stu, _ = await _linked_student(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, hold_results=False, subject_id=subj.id, term="Term 1")
    await _attempt(db, org, exam, stu.id, score=10)  # 50% → C

    res = await feed_gradebook(exam.id, request=None, db=db, current_user=staff)
    assert res["fed"] == 1
    assert (await _grades_for(db, org, exam))[0].grade_letter == "C"


async def test_exam_results_exposes_gradebook_state(db, org):
    staff = await _staff(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, subject_id=subj.id, term=None)  # missing term
    data = await exam_results(exam.id, db=db, current_user=staff)
    assert data["gradebook"]["fed_count"] == 0
    assert "term" in data["gradebook"]["block_reason"].lower()


# ── Loop closed: parents see a fed grade only after the gradebook publish ─────────

async def test_report_card_shows_cbt_grade_only_after_publish(db, org):
    staff = await _staff(db, org)
    stu, stu_user = await _linked_student(db, org)
    subj = await _subject(db, org)
    exam = await _exam(db, org, staff, hold_results=True, subject_id=subj.id, term="Term 1")
    await _attempt(db, org, exam, stu.id, score=15)  # 75% → A
    assert not stu_user.has_permission("school:students:read")  # sees published grades only

    # publish CBT → DRAFT grade fed → parent/student report card still hides it
    await publish_exam_results(exam.id, request=None, db=db, current_user=staff)
    card = await get_report_card(stu.id, term="Term 1", db=db, current_user=stu_user)
    assert card["grades"] == []

    # staff release the grade to parents (the gradebook's own publish step)
    g = (await _grades_for(db, org, exam))[0]
    g.status = GradeStatus.PUBLISHED
    await db.commit()
    card2 = await get_report_card(stu.id, term="Term 1", db=db, current_user=stu_user)
    assert len(card2["grades"]) == 1
    assert card2["grades"][0]["score"] == 75 and card2["grades"][0]["grade_letter"] == "A"


# ── RBAC ──────────────────────────────────────────────────────────────────────────

async def test_feed_is_staff_write_only(db, org):
    staff = await _staff(db, org)
    assert staff.has_permission("school:write")
    _, stu_user = await _linked_student(db, org)
    assert not stu_user.has_permission("school:write")  # students can't feed the gradebook
