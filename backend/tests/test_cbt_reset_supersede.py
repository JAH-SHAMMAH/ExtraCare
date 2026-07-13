"""CBT reset = soft delete (supersede), and how it interacts with the attempt
limit + Result Manager. Reset frees a slot (superseded doesn't count), isn't
resumed, is excluded from a student's list and from stats, but is still SHOWN
(badged) in the Result Manager.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import CBTExam, CBTAttempt, ExamStatus, AttemptStatus, Student
from app.routers.modules.cbt import (
    reset_attempt, start_attempt, exam_results, list_attempts,
    reset_exam_attempts, set_attempt_remark_note,
)

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


async def _student(db, org) -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
                first_name="S", last_name="X", org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _exam(db, org, staff, *, max_attempts=1, total_points=2) -> CBTExam:
    exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", created_by=staff.id, org_id=org.id,
                   status=ExamStatus.PUBLISHED, total_points=total_points, max_attempts=max_attempts)
    db.add(exam)
    await db.commit()
    return exam


def _attempt(exam, student_id, org, *, status=AttemptStatus.GRADED, score=2, superseded=False):
    return CBTAttempt(
        id=str(uuid.uuid4()), exam_id=exam.id, student_id=student_id, max_score=2, score=score,
        status=status, started_at=datetime.now(timezone.utc), org_id=org.id,
        superseded_at=datetime.now(timezone.utc) if superseded else None,
    )


async def test_reset_frees_attempt_slot(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff, max_attempts=1)
    att = _attempt(exam, stu.id, org, status=AttemptStatus.GRADED)
    db.add(att)
    await db.commit()

    # at the cap -> a new start is blocked
    with pytest.raises(HTTPException) as exc:
        await start_attempt(exam.id, student_id=stu.id, db=db, current_user=staff)
    assert exc.value.status_code == 409

    # reset supersedes the attempt -> the slot frees up -> retake allowed
    await reset_attempt(att.id, request=None, db=db, current_user=staff)
    res = await start_attempt(exam.id, student_id=stu.id, db=db, current_user=staff)
    assert res["status"] == "in_progress"


async def test_superseded_inprogress_not_resumed(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff, max_attempts=1)
    old_ip = _attempt(exam, stu.id, org, status=AttemptStatus.IN_PROGRESS, superseded=True)
    db.add(old_ip)
    await db.commit()
    # the superseded in-progress attempt is NOT resumed — a fresh one starts
    res = await start_attempt(exam.id, student_id=stu.id, db=db, current_user=staff)
    assert res["id"] != old_ip.id and res["status"] == "in_progress"


async def test_superseded_shown_but_excluded_from_stats(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff, total_points=2)
    active = _attempt(exam, stu.id, org, status=AttemptStatus.GRADED, score=2)          # 100% pass
    old = _attempt(exam, stu.id, org, status=AttemptStatus.GRADED, score=0, superseded=True)  # would drag stats
    db.add_all([active, old])
    await db.commit()

    res = await exam_results(exam.id, db=db, current_user=staff)
    # stats count only the active attempt
    assert res["stats"]["attempts"] == 1 and res["stats"]["pass_rate"] == 100
    # but BOTH rows are shown, the reset one flagged
    by_id = {r["id"]: r for r in res["attempts"]}
    assert len(res["attempts"]) == 2
    assert by_id[old.id]["superseded"] is True and by_id[active.id]["superseded"] is False


async def test_list_attempts_excludes_superseded(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff)
    db.add_all([
        _attempt(exam, stu.id, org, status=AttemptStatus.GRADED),
        _attempt(exam, stu.id, org, status=AttemptStatus.GRADED, superseded=True),
    ])
    await db.commit()
    res = await list_attempts(exam_id=exam.id, student_id=None, db=db, current_user=staff)
    assert len(res["items"]) == 1 and all("superseded" not in i or i for i in res["items"])


# ── Admin CBT Reset (bulk) + Admin Test Remark ────────────────────────────────────

async def test_bulk_reset_supersedes_all_active(db, org):
    staff = await _staff(db, org)
    s1, s2 = await _student(db, org), await _student(db, org)
    exam = await _exam(db, org, staff)
    a1 = _attempt(exam, s1.id, org, status=AttemptStatus.GRADED)
    a2 = _attempt(exam, s2.id, org, status=AttemptStatus.GRADED)
    already = _attempt(exam, s1.id, org, status=AttemptStatus.GRADED, superseded=True)
    db.add_all([a1, a2, already])
    await db.commit()

    res = await reset_exam_attempts(exam.id, request=None, db=db, current_user=staff)
    assert res["reset"] == 2   # only the two ACTIVE attempts (the already-superseded one is left)
    # every active attempt now superseded → Result Manager stats show none active
    rr = await exam_results(exam.id, db=db, current_user=staff)
    assert rr["stats"]["attempts"] == 0


async def test_set_result_remark_note(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff)
    att = _attempt(exam, stu.id, org, status=AttemptStatus.GRADED)
    db.add(att)
    await db.commit()

    out = await set_attempt_remark_note(att.id, {"remark_note": "  Great improvement.  "},
                                        request=None, db=db, current_user=staff)
    assert out["remark_note"] == "Great improvement."   # trimmed
    # surfaces in the Result Manager rows
    rr = await exam_results(exam.id, db=db, current_user=staff)
    assert next(r for r in rr["attempts"] if r["id"] == att.id)["remark_note"] == "Great improvement."
    # clearing (blank) → None
    cleared = await set_attempt_remark_note(att.id, {"remark_note": "   "},
                                            request=None, db=db, current_user=staff)
    assert cleared["remark_note"] is None
