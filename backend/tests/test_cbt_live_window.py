"""
Pure-function coverage of CBT live-window enforcement. `_is_live` is the
single predicate that gates `start_attempt` — a bug here either lets students
start closed exams or blocks them during the scheduled window.
"""

from datetime import datetime, timezone, timedelta

import pytest

from app.routers.modules.cbt import _is_live
from app.models.modules.school import CBTExam, ExamStatus


NOW = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)


def _exam(**kw) -> CBTExam:
    defaults = dict(
        title="T",
        status=ExamStatus.PUBLISHED,
        start_time=NOW - timedelta(hours=1),
        end_time=NOW + timedelta(hours=1),
        duration_minutes=60,
        created_by="u",
        org_id="o",
    )
    defaults.update(kw)
    return CBTExam(**defaults)


def test_published_during_window_is_live():
    assert _is_live(_exam(), NOW) is True


def test_active_during_window_is_live():
    assert _is_live(_exam(status=ExamStatus.ACTIVE), NOW) is True


def test_draft_never_live():
    assert _is_live(_exam(status=ExamStatus.DRAFT), NOW) is False


def test_closed_never_live():
    assert _is_live(_exam(status=ExamStatus.CLOSED), NOW) is False


def test_before_start_is_not_live():
    e = _exam(start_time=NOW + timedelta(minutes=5))
    assert _is_live(e, NOW) is False


def test_after_end_is_not_live():
    e = _exam(end_time=NOW - timedelta(minutes=5))
    assert _is_live(e, NOW) is False


def test_no_start_no_end_is_live_when_published():
    """Exams without a scheduled window rely on status alone."""
    e = _exam(start_time=None, end_time=None)
    assert _is_live(e, NOW) is True


def test_only_start_set_before_is_not_live():
    e = _exam(start_time=NOW + timedelta(minutes=1), end_time=None)
    assert _is_live(e, NOW) is False


def test_only_end_set_after_is_not_live():
    e = _exam(start_time=None, end_time=NOW - timedelta(minutes=1))
    assert _is_live(e, NOW) is False


@pytest.mark.parametrize("delta_secs", [-1, 0, 1])
def test_boundary_at_start(delta_secs):
    """At exactly start_time the exam is live (>= boundary handled inclusively)."""
    e = _exam(start_time=NOW + timedelta(seconds=delta_secs))
    expected = delta_secs <= 0
    assert _is_live(e, NOW) is expected


# ── End to end: does start_attempt actually enforce the window? ────────────────
#
# Everything above tests `_is_live` as a PURE FUNCTION with in-memory objects,
# and it passed while the handler was broken. The bug it missed: `_is_live`
# compared exam.start_time against an aware `now` without normalising, so a
# PERSISTED exam whose timestamps came back naive raised TypeError -> HTTP 500
# instead of the clean 400 a closed exam should give. Postgres hands back aware
# values and masked it; SQLite does not.
#
# These drive the real handler against a stored exam, which is the only place
# that class of bug can show up.

import uuid as _uuid
from datetime import timedelta as _timedelta

from fastapi import HTTPException as _HTTPException
from sqlalchemy import select as _select
from sqlalchemy.orm import selectinload as _selectinload

from app.models.modules.school import SchoolClass as _SchoolClass, Student as _Student
from app.models.role import Role as _Role, SCHOOL_PERMISSION_PRESETS as _PRESETS
from app.models.user import User as _User, UserStatus as _UserStatus
from app.routers.modules.cbt import start_attempt as _start_attempt


async def _sitting_student(db, org):
    """A student in a class, able to sit that class's exams."""
    cls = _SchoolClass(id=str(_uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    db.add(cls)
    await db.commit()
    email = f"pupil-{_uuid.uuid4().hex[:6]}@example.com"
    role = _Role(id=str(_uuid.uuid4()), name="student", slug=f"s-{_uuid.uuid4().hex[:6]}",
                 permissions=list(_PRESETS["student"]), org_id=org.id, is_system=False)
    u = _User(id=str(_uuid.uuid4()), email=email, full_name="Pupil",
              status=_UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    s = _Student(id=str(_uuid.uuid4()), student_id=f"S-{_uuid.uuid4().hex[:5]}", first_name="P",
                 last_name="Q", email=email, user_id=u.id, class_id=cls.id, org_id=org.id)
    db.add_all([role, u, s])
    await db.commit()
    return cls, s, u


async def _persisted_exam(db, org, cls, author, *, start, end, status=ExamStatus.PUBLISHED):
    """Store an exam, then read it back OFF STORAGE — the round trip is the point.

    expunge_all() is load-bearing, not tidiness. Without it the identity map
    hands back the same Python object, timestamps still tz-aware, and the test
    passes against the very bug it exists to catch: SQLite drops tzinfo on the
    way out, and only a genuine reload reproduces the naive value that made
    `_is_live` raise TypeError.
    """
    e = CBTExam(id=str(_uuid.uuid4()), title="Windowed", status=status, total_points=1.0,
                duration_minutes=60, start_time=start, end_time=end,
                class_id=cls.id, created_by=author.id, org_id=org.id)
    db.add(e)
    await db.commit()
    db.expunge_all()
    return (await db.execute(_select(CBTExam).where(CBTExam.id == e.id))).scalar_one()


async def _reload_user(db, user):
    return (await db.execute(
        _select(_User).options(_selectinload(_User.roles)).where(_User.id == user.id)
    )).scalar_one()


@pytest.mark.parametrize("offset_hours,expected_reason", [
    ((2, 3), "before the window opens"),
    ((-3, -2), "after the window closes"),
])
async def test_start_attempt_refuses_outside_the_window(db, org, offset_hours, expected_reason):
    """A closed window must give a clean 400, not a 500."""
    cls, stu, user = await _sitting_student(db, org)
    now = datetime.now(timezone.utc)
    lo, hi = offset_hours
    exam = await _persisted_exam(db, org, cls, user,
                                 start=now + _timedelta(hours=lo),
                                 end=now + _timedelta(hours=hi))

    with pytest.raises(_HTTPException) as exc:
        await _start_attempt(exam.id, student_id=None, db=db,
                             current_user=await _reload_user(db, user))
    assert exc.value.status_code == 400, f"{expected_reason}: expected 400"
    assert "not currently live" in exc.value.detail


async def test_start_attempt_allows_inside_the_window(db, org):
    cls, stu, user = await _sitting_student(db, org)
    now = datetime.now(timezone.utc)
    exam = await _persisted_exam(db, org, cls, user,
                                 start=now - _timedelta(hours=1),
                                 end=now + _timedelta(hours=1))

    out = await _start_attempt(exam.id, student_id=None, db=db,
                               current_user=await _reload_user(db, user))
    assert out["exam_id"] == exam.id


async def test_start_attempt_allows_an_unscheduled_published_exam(db, org):
    """No window set — status alone decides. This is every exam in production
    today, which is why the naive-datetime path was never hit there."""
    cls, stu, user = await _sitting_student(db, org)
    exam = await _persisted_exam(db, org, cls, user, start=None, end=None)

    out = await _start_attempt(exam.id, student_id=None, db=db,
                               current_user=await _reload_user(db, user))
    assert out["exam_id"] == exam.id


@pytest.mark.parametrize("status", [ExamStatus.DRAFT, ExamStatus.CLOSED])
async def test_start_attempt_refuses_by_status_even_inside_the_window(db, org, status):
    cls, stu, user = await _sitting_student(db, org)
    now = datetime.now(timezone.utc)
    exam = await _persisted_exam(db, org, cls, user,
                                 start=now - _timedelta(hours=1),
                                 end=now + _timedelta(hours=1), status=status)

    with pytest.raises(_HTTPException) as exc:
        await _start_attempt(exam.id, student_id=None, db=db,
                             current_user=await _reload_user(db, user))
    assert exc.value.status_code == 400
