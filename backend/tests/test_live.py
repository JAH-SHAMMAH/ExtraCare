"""Tests for the Livestream module.

REST-only coverage — start/end/list/get with tenant isolation and
host-only end authorisation. The signaling WebSocket is a thin forwarder
that exercises the same `_auth_ws` + `_load_session` path as the REST
handlers, so the policy decisions it relies on are covered here.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.routers.live import (
    start_session, end_session, list_sessions, get_session, ice_config,
    upload_recording, list_recordings, session_analytics,
    start_from_timetable, timetable_today, _mark_class_attendance,
)
from app.schemas.live import LiveSessionCreate
from app.models.live import LiveAttendance, LiveRecording


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def second_user(db, org) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="peer@example.com",
        full_name="Peer Two",
        status=UserStatus.ACTIVE,
        org_id=org.id,
    )
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def other_org(db) -> Organization:
    o = Organization(
        id=str(uuid.uuid4()),
        name="Other Org",
        slug=f"other-{uuid.uuid4().hex[:8]}",
        industry=IndustryType.SCHOOL,
        modules_enabled=["school"],
    )
    db.add(o)
    await db.commit()
    return o


@pytest_asyncio.fixture
async def other_org_user(db, other_org) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="outsider@example.com",
        full_name="Other Org User",
        status=UserStatus.ACTIVE,
        org_id=other_org.id,
    )
    db.add(u)
    await db.commit()
    return u


# ── Start ────────────────────────────────────────────────────────────────────

async def test_start_creates_active_session(db, teacher):
    s = await start_session(
        data=LiveSessionCreate(title="Maths Live"),
        db=db, current_user=teacher,
    )
    assert s.is_active is True
    assert s.title == "Maths Live"
    assert s.host_user_id == teacher.id
    assert s.org_id == teacher.org_id
    assert s.ended_at is None


async def test_start_rejects_blank_title(db, teacher):
    with pytest.raises(Exception):  # ValidationError or HTTP 422
        await start_session(
            data=LiveSessionCreate(title="   "),
            db=db, current_user=teacher,
        )


# ── End ──────────────────────────────────────────────────────────────────────

async def test_host_can_end_session(db, teacher):
    s = await start_session(
        data=LiveSessionCreate(title="x"), db=db, current_user=teacher,
    )
    ended = await end_session(session_id=s.id, db=db, current_user=teacher)
    assert ended.is_active is False
    assert ended.ended_at is not None


async def test_non_host_cannot_end_session(db, teacher, second_user):
    s = await start_session(
        data=LiveSessionCreate(title="x"), db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await end_session(session_id=s.id, db=db, current_user=second_user)
    assert exc.value.status_code == 403


async def test_end_is_idempotent(db, teacher):
    s = await start_session(
        data=LiveSessionCreate(title="x"), db=db, current_user=teacher,
    )
    first = await end_session(session_id=s.id, db=db, current_user=teacher)
    # Second call should succeed (no-op); is_active stays false.
    second = await end_session(session_id=s.id, db=db, current_user=teacher)
    assert first.is_active is False
    assert second.is_active is False


# ── Listing ──────────────────────────────────────────────────────────────────

async def test_list_default_shows_only_active(db, teacher):
    a = await start_session(
        data=LiveSessionCreate(title="active"), db=db, current_user=teacher,
    )
    b = await start_session(
        data=LiveSessionCreate(title="closed"), db=db, current_user=teacher,
    )
    await end_session(session_id=b.id, db=db, current_user=teacher)

    rows = await list_sessions(active_only=True, db=db, current_user=teacher)
    assert [r.id for r in rows] == [a.id]

    all_rows = await list_sessions(active_only=False, db=db, current_user=teacher)
    assert {r.id for r in all_rows} == {a.id, b.id}


# ── Tenant isolation ─────────────────────────────────────────────────────────

async def test_other_org_cannot_see_session(db, teacher, other_org_user):
    s = await start_session(
        data=LiveSessionCreate(title="secret"), db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await get_session(session_id=s.id, db=db, current_user=other_org_user)
    assert exc.value.status_code == 404


async def test_list_is_org_scoped(db, teacher, other_org_user):
    await start_session(
        data=LiveSessionCreate(title="org-a"), db=db, current_user=teacher,
    )
    rows_b = await list_sessions(active_only=True, db=db, current_user=other_org_user)
    assert rows_b == []
    rows_a = await list_sessions(active_only=True, db=db, current_user=teacher)
    assert len(rows_a) == 1


async def test_other_org_cannot_end_session(db, teacher, other_org_user):
    s = await start_session(
        data=LiveSessionCreate(title="x"), db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await end_session(session_id=s.id, db=db, current_user=other_org_user)
    # 404 (not 403) — tenant isolation runs before host check.
    assert exc.value.status_code == 404


# ── Roster gate ──────────────────────────────────────────────────────────────

async def test_class_bound_session_allows_enrolled_student(
    db, teacher, school_class, student, student_user,
):
    s = await start_session(
        data=LiveSessionCreate(title="Year 10 Maths", class_id=school_class.id),
        db=db, current_user=teacher,
    )
    # Enrolled student joins via the student_user fixture (shared email).
    resolved = await get_session(session_id=s.id, db=db, current_user=student_user)
    assert resolved.id == s.id


async def test_class_bound_session_hides_from_non_roster(
    db, teacher, school_class, student, unlinked_user,
):
    s = await start_session(
        data=LiveSessionCreate(title="Year 10 Maths", class_id=school_class.id),
        db=db, current_user=teacher,
    )
    # Unlinked staff: no roster membership, no admin permission. Must 404
    # (don't leak existence of private class sessions).
    with pytest.raises(HTTPException) as exc:
        await get_session(session_id=s.id, db=db, current_user=unlinked_user)
    assert exc.value.status_code == 404


async def test_list_hides_class_bound_sessions_from_non_roster(
    db, teacher, school_class, student, unlinked_user,
):
    await start_session(
        data=LiveSessionCreate(title="private", class_id=school_class.id),
        db=db, current_user=teacher,
    )
    await start_session(
        data=LiveSessionCreate(title="open"),
        db=db, current_user=teacher,
    )
    rows = await list_sessions(active_only=True, db=db, current_user=unlinked_user)
    assert {r.title for r in rows} == {"open"}


async def test_open_session_still_accessible_to_any_org_member(
    db, teacher, unlinked_user,
):
    s = await start_session(
        data=LiveSessionCreate(title="assembly"),
        db=db, current_user=teacher,
    )
    got = await get_session(session_id=s.id, db=db, current_user=unlinked_user)
    assert got.id == s.id


# ── ICE config ───────────────────────────────────────────────────────────────

async def test_ice_config_returns_stun_when_turn_unset(teacher, monkeypatch):
    from app.config import get_settings
    get_settings.cache_clear()
    cfg = await ice_config(current_user=teacher)
    get_settings.cache_clear()
    urls = [u for s in cfg["iceServers"] for u in ([s["urls"]] if isinstance(s["urls"], str) else s["urls"])]
    assert any("stun:" in u for u in urls)
    assert not any("turn:" in u for u in urls)


async def test_ice_config_includes_turn_with_ephemeral_creds(teacher, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TURN_URLS", "turn:turn.example.com:3478")
    monkeypatch.setenv("TURN_SECRET", "test-secret")
    get_settings.cache_clear()
    cfg = await ice_config(current_user=teacher)
    get_settings.cache_clear()
    turn = [s for s in cfg["iceServers"] if any("turn:" in u for u in (s["urls"] if isinstance(s["urls"], list) else [s["urls"]]))]
    assert len(turn) == 1
    assert turn[0]["username"].endswith(f":{teacher.id}")
    assert turn[0]["credential"]  # HMAC base64 string, non-empty


# ── Recordings ───────────────────────────────────────────────────────────────

class _FakeUpload:
    """Minimal UploadFile-compatible stub. Streams one chunk then EOFs."""

    def __init__(self, data: bytes, content_type: str = "video/webm", filename: str = "rec.webm"):
        self._data = data
        self._pos = 0
        self.content_type = content_type
        self.filename = filename

    async def read(self, n: int = -1) -> bytes:
        if self._pos >= len(self._data):
            return b""
        if n < 0 or self._pos + n >= len(self._data):
            out = self._data[self._pos:]
            self._pos = len(self._data)
            return out
        out = self._data[self._pos:self._pos + n]
        self._pos += n
        return out


async def _bump_to_pro(db, org_id: str) -> None:
    """Flip the test org onto a tier with the Livestream feature + quota.
    The FREE tier has no recording storage, so quota-gated handlers 402
    before they run the logic under test."""
    from sqlalchemy import update as sa_update
    from app.models.organization import Organization, SubscriptionTier
    await db.execute(
        sa_update(Organization)
        .where(Organization.id == org_id)
        .values(subscription_tier=SubscriptionTier.PRO)
    )
    await db.commit()


async def test_host_can_upload_recording(db, teacher, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()
    await _bump_to_pro(db, teacher.org_id)

    s = await start_session(
        data=LiveSessionCreate(title="rec"), db=db, current_user=teacher,
    )
    file = _FakeUpload(b"\x00\x01\x02\x03" * 100, content_type="video/webm")
    rec = await upload_recording(
        session_id=s.id, file=file, duration_seconds=42,
        db=db, current_user=teacher,
    )
    get_settings.cache_clear()
    assert rec.session_id == s.id
    assert rec.file_size == 400
    assert rec.duration_seconds == 42
    assert rec.file_url.startswith("/uploads/")


async def test_non_host_cannot_upload_recording(db, teacher, second_user, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    s = await start_session(
        data=LiveSessionCreate(title="rec"), db=db, current_user=teacher,
    )
    file = _FakeUpload(b"\x00\x01", content_type="video/webm")
    with pytest.raises(HTTPException) as exc:
        await upload_recording(
            session_id=s.id, file=file, duration_seconds=None,
            db=db, current_user=second_user,
        )
    get_settings.cache_clear()
    assert exc.value.status_code == 403


async def test_upload_rejects_unsupported_mime(db, teacher, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    s = await start_session(
        data=LiveSessionCreate(title="rec"), db=db, current_user=teacher,
    )
    file = _FakeUpload(b"junk", content_type="application/x-evil")
    with pytest.raises(HTTPException) as exc:
        await upload_recording(
            session_id=s.id, file=file, duration_seconds=None,
            db=db, current_user=teacher,
        )
    get_settings.cache_clear()
    assert exc.value.status_code == 415


async def test_recording_flag_surfaces_on_session(db, teacher, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()
    await _bump_to_pro(db, teacher.org_id)

    s = await start_session(
        data=LiveSessionCreate(title="rec"), db=db, current_user=teacher,
    )
    before = await get_session(session_id=s.id, db=db, current_user=teacher)
    assert before.has_recording is False

    await upload_recording(
        session_id=s.id, file=_FakeUpload(b"x" * 10), duration_seconds=1,
        db=db, current_user=teacher,
    )
    after = await get_session(session_id=s.id, db=db, current_user=teacher)
    get_settings.cache_clear()
    assert after.has_recording is True


# ── Analytics ────────────────────────────────────────────────────────────────

async def test_analytics_host_only(db, teacher, second_user):
    s = await start_session(
        data=LiveSessionCreate(title="x"), db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await session_analytics(session_id=s.id, db=db, current_user=second_user)
    assert exc.value.status_code == 403


async def test_analytics_aggregates_attendance(db, teacher, second_user):
    from datetime import datetime, timedelta, timezone as tz
    s = await start_session(
        data=LiveSessionCreate(title="x"), db=db, current_user=teacher,
    )
    # Two completed sessions + one still-live row.
    t0 = datetime.now(tz.utc)
    db.add_all([
        LiveAttendance(
            org_id=teacher.org_id, session_id=s.id, user_id=second_user.id,
            joined_at=t0, left_at=t0 + timedelta(seconds=60), duration_seconds=60,
        ),
        LiveAttendance(
            org_id=teacher.org_id, session_id=s.id, user_id=second_user.id,
            joined_at=t0 + timedelta(seconds=120),
            left_at=t0 + timedelta(seconds=180), duration_seconds=60,
        ),
        LiveAttendance(
            org_id=teacher.org_id, session_id=s.id, user_id=teacher.id,
            joined_at=t0,  # still live → no left_at
        ),
    ])
    await db.commit()

    result = await session_analytics(session_id=s.id, db=db, current_user=teacher)
    assert result.total_joins == 3
    assert result.unique_viewers == 2
    assert result.average_watch_seconds == 60  # only the two completed rows feed the avg


# ── Timetable integration ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def subject(db, org, teacher):
    from app.models.modules.school import Subject
    s = Subject(
        id=str(uuid.uuid4()), name="Mathematics", code="MATH",
        teacher_id=teacher.id, org_id=org.id,
    )
    db.add(s)
    await db.commit()
    return s


@pytest_asyncio.fixture
async def timetable_slot(db, org, school_class, subject, teacher):
    from app.models.modules.school import Timetable
    from datetime import datetime, timezone as tz
    dow = datetime.now(tz.utc).weekday()  # current day → is_current passes
    t = Timetable(
        id=str(uuid.uuid4()),
        class_id=school_class.id,
        subject_id=subject.id,
        day_of_week=dow,
        start_time="00:00",
        end_time="23:59",
        teacher_id=teacher.id,
        org_id=org.id,
    )
    db.add(t)
    await db.commit()
    return t


async def test_start_from_timetable_creates_bound_session(db, teacher, timetable_slot):
    s = await start_from_timetable(
        timetable_id=timetable_slot.id, db=db, current_user=teacher,
    )
    assert s.class_id == timetable_slot.class_id
    assert s.subject_id == timetable_slot.subject_id
    assert s.timetable_id == timetable_slot.id
    assert s.is_active is True


async def test_start_from_timetable_is_idempotent(db, teacher, timetable_slot):
    first = await start_from_timetable(
        timetable_id=timetable_slot.id, db=db, current_user=teacher,
    )
    second = await start_from_timetable(
        timetable_id=timetable_slot.id, db=db, current_user=teacher,
    )
    assert first.id == second.id  # returns the live one instead of duplicating


async def test_start_from_timetable_rejects_non_teacher(db, second_user, timetable_slot):
    with pytest.raises(HTTPException) as exc:
        await start_from_timetable(
            timetable_id=timetable_slot.id, db=db, current_user=second_user,
        )
    assert exc.value.status_code == 403


async def test_timetable_today_shows_teacher_slots(db, teacher, timetable_slot):
    slots = await timetable_today(db=db, current_user=teacher)
    assert len(slots) == 1
    assert slots[0].timetable_id == timetable_slot.id
    assert slots[0].is_current is True
    assert slots[0].can_host is True
    assert slots[0].live_session_id is None  # no active session yet


async def test_timetable_today_surfaces_live_session_id(db, teacher, timetable_slot):
    s = await start_from_timetable(
        timetable_id=timetable_slot.id, db=db, current_user=teacher,
    )
    slots = await timetable_today(db=db, current_user=teacher)
    assert slots[0].live_session_id == s.id


# ── Attendance bridge ────────────────────────────────────────────────────────

async def test_mark_class_attendance_writes_record(
    db, teacher, school_class, student, student_user,
):
    from app.models.modules.school import AttendanceRecord
    from datetime import datetime, timezone as tz
    s = await start_session(
        data=LiveSessionCreate(title="Live", class_id=school_class.id),
        db=db, current_user=teacher,
    )
    # Reload as a full LiveSession row (handler returns the Pydantic response).
    from sqlalchemy import select as sa_select
    from app.models.live import LiveSession
    row = (await db.execute(
        sa_select(LiveSession).where(LiveSession.id == s.id)
    )).scalar_one()

    await _mark_class_attendance(
        db, user=student_user, session=row, when=datetime.now(tz.utc),
    )
    await db.commit()

    rows = (await db.execute(
        sa_select(AttendanceRecord).where(
            AttendanceRecord.student_id == student.id,
            AttendanceRecord.class_id == school_class.id,
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].notes and s.id in rows[0].notes


async def test_mark_class_attendance_is_idempotent_per_day(
    db, teacher, school_class, student, student_user,
):
    from app.models.modules.school import AttendanceRecord
    from datetime import datetime, timezone as tz
    from sqlalchemy import select as sa_select
    from app.models.live import LiveSession

    s = await start_session(
        data=LiveSessionCreate(title="Live", class_id=school_class.id),
        db=db, current_user=teacher,
    )
    row = (await db.execute(
        sa_select(LiveSession).where(LiveSession.id == s.id)
    )).scalar_one()

    now = datetime.now(tz.utc)
    await _mark_class_attendance(db, user=student_user, session=row, when=now)
    await db.commit()
    await _mark_class_attendance(db, user=student_user, session=row, when=now)
    await db.commit()

    count = (await db.execute(
        sa_select(AttendanceRecord).where(AttendanceRecord.student_id == student.id)
    )).scalars().all()
    assert len(count) == 1


async def test_mark_class_attendance_skips_non_student_users(
    db, teacher, school_class, unlinked_user,
):
    from app.models.modules.school import AttendanceRecord
    from datetime import datetime, timezone as tz
    from sqlalchemy import select as sa_select
    from app.models.live import LiveSession

    s = await start_session(
        data=LiveSessionCreate(title="Live", class_id=school_class.id),
        db=db, current_user=teacher,
    )
    row = (await db.execute(
        sa_select(LiveSession).where(LiveSession.id == s.id)
    )).scalar_one()

    await _mark_class_attendance(
        db, user=unlinked_user, session=row, when=datetime.now(tz.utc),
    )
    await db.commit()

    rows = (await db.execute(sa_select(AttendanceRecord))).scalars().all()
    assert rows == []  # unlinked staff never get marked present


# ── Monetization ─────────────────────────────────────────────────────────────

async def test_recording_quota_402_when_exceeded(db, teacher, tmp_path, monkeypatch):
    """When the org's stored bytes already meet the plan cap, the next
    upload must 402 rather than write a byte to disk."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    # Bump to PRO (10 GB cap) and then seed a fake existing-recording row
    # at the cap so the next upload is guaranteed over.
    await _bump_to_pro(db, teacher.org_id)
    from app.core.plans import plan_for
    from app.models.organization import Organization, SubscriptionTier
    cap_mb = plan_for(SubscriptionTier.PRO).recording_storage_mb
    cap_bytes = cap_mb * 1024 * 1024

    s = await start_session(
        data=LiveSessionCreate(title="rec"), db=db, current_user=teacher,
    )
    db.add(LiveRecording(
        org_id=teacher.org_id, session_id=s.id,
        file_path="x", file_size=cap_bytes,
        mime_type="video/webm", created_by=teacher.id,
    ))
    await db.commit()

    file = _FakeUpload(b"\x00" * 10, content_type="video/webm")
    with pytest.raises(HTTPException) as exc:
        await upload_recording(
            session_id=s.id, file=file, duration_seconds=None,
            db=db, current_user=teacher,
        )
    get_settings.cache_clear()
    assert exc.value.status_code == 402
    assert exc.value.detail["reason"] == "recording_storage_exceeded"


async def test_livestream_flag_enabled_on_pro(db, teacher):
    """PRO tier ships with the `livestream` flag on by default so the
    frontend can avoid showing a gated entry-point when it shouldn't."""
    from app.core.features import has_feature
    from app.models.organization import Organization
    from sqlalchemy import select as sa_select
    await _bump_to_pro(db, teacher.org_id)
    org = (await db.execute(
        sa_select(Organization).where(Organization.id == teacher.org_id)
    )).scalar_one()
    assert has_feature(org, "livestream") is True


async def test_livestream_flag_disabled_on_free(db, org):
    from app.core.features import has_feature
    assert has_feature(org, "livestream") is False


# ── Reconnect semantics ──────────────────────────────────────────────────────

async def test_viewer_join_creates_fresh_attendance_row(db, teacher, student_user):
    """First-time join writes a new row with joined_at set and left_at null."""
    from datetime import datetime, timezone as tz
    from sqlalchemy import select as sa_select
    from app.models.live import LiveSession
    from app.routers.live import _record_viewer_join

    s = await start_session(
        data=LiveSessionCreate(title="Live"), db=db, current_user=teacher,
    )
    row = (await db.execute(
        sa_select(LiveSession).where(LiveSession.id == s.id)
    )).scalar_one()

    now = datetime.now(tz.utc)
    att_id, joined_at = await _record_viewer_join(
        db, user=student_user, session=row, now=now,
    )

    rows = (await db.execute(sa_select(LiveAttendance))).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == att_id
    assert rows[0].left_at is None
    assert joined_at == now


async def test_viewer_reconnect_resumes_open_row(db, teacher, student_user):
    """A stale (open) row should be reopened, not duplicated."""
    from datetime import datetime, timezone as tz
    from sqlalchemy import select as sa_select
    from app.models.live import LiveSession
    from app.routers.live import _record_viewer_join

    s = await start_session(
        data=LiveSessionCreate(title="Live"), db=db, current_user=teacher,
    )
    row = (await db.execute(
        sa_select(LiveSession).where(LiveSession.id == s.id)
    )).scalar_one()

    first_now = datetime.now(tz.utc)
    first_id, first_joined = await _record_viewer_join(
        db, user=student_user, session=row, now=first_now,
    )
    # Simulate an abrupt drop (no left_at written) → immediate reconnect.
    from datetime import timedelta
    reconnect_now = first_now + timedelta(seconds=5)
    second_id, second_joined = await _record_viewer_join(
        db, user=student_user, session=row, now=reconnect_now,
    )

    assert second_id == first_id
    assert second_joined == first_joined  # original join is preserved
    rows = (await db.execute(sa_select(LiveAttendance))).scalars().all()
    assert len(rows) == 1


async def test_viewer_reconnect_within_window_resumes_closed_row(db, teacher, student_user):
    """A row closed <30s ago should be reopened on reconnect."""
    from datetime import datetime, timedelta, timezone as tz
    from sqlalchemy import select as sa_select, update as sa_update
    from app.models.live import LiveSession
    from app.routers.live import _record_viewer_join

    s = await start_session(
        data=LiveSessionCreate(title="Live"), db=db, current_user=teacher,
    )
    row = (await db.execute(
        sa_select(LiveSession).where(LiveSession.id == s.id)
    )).scalar_one()

    first_now = datetime.now(tz.utc)
    first_id, _ = await _record_viewer_join(
        db, user=student_user, session=row, now=first_now,
    )
    # Simulate a graceful close 5s later.
    closed_at = first_now + timedelta(seconds=5)
    await db.execute(
        sa_update(LiveAttendance)
        .where(LiveAttendance.id == first_id)
        .values(left_at=closed_at, duration_seconds=5)
    )
    await db.commit()

    # Reconnect 10s after close — still inside the 30s window.
    reconnect_now = closed_at + timedelta(seconds=10)
    second_id, _ = await _record_viewer_join(
        db, user=student_user, session=row, now=reconnect_now,
    )
    assert second_id == first_id
    rows = (await db.execute(sa_select(LiveAttendance))).scalars().all()
    assert len(rows) == 1
    # left_at is cleared on resume so disconnect handler recomputes duration.
    assert rows[0].left_at is None


async def test_viewer_reconnect_after_window_creates_new_row(db, teacher, student_user):
    """A row closed >30s ago is treated as a distinct session."""
    from datetime import datetime, timedelta, timezone as tz
    from sqlalchemy import select as sa_select, update as sa_update
    from app.models.live import LiveSession
    from app.routers.live import _record_viewer_join

    s = await start_session(
        data=LiveSessionCreate(title="Live"), db=db, current_user=teacher,
    )
    row = (await db.execute(
        sa_select(LiveSession).where(LiveSession.id == s.id)
    )).scalar_one()

    first_now = datetime.now(tz.utc)
    first_id, _ = await _record_viewer_join(
        db, user=student_user, session=row, now=first_now,
    )
    closed_at = first_now + timedelta(seconds=5)
    await db.execute(
        sa_update(LiveAttendance)
        .where(LiveAttendance.id == first_id)
        .values(left_at=closed_at, duration_seconds=5)
    )
    await db.commit()

    # Reconnect well after the 30s resume window → distinct row.
    rejoin_now = closed_at + timedelta(minutes=5)
    second_id, _ = await _record_viewer_join(
        db, user=student_user, session=row, now=rejoin_now,
    )
    assert second_id != first_id
    rows = (await db.execute(sa_select(LiveAttendance))).scalars().all()
    assert len(rows) == 2


async def test_signaling_register_viewer_replaces_stale_ws(db, teacher):
    """When the same user_id reconnects, the new WS should replace the old
    entry and the stale socket should be closed. Viewer count stays at 1."""
    from app.routers.live import SignalingManager

    mgr = SignalingManager()

    class FakeWS:
        def __init__(self):
            self.closed = False
            self.close_code: int | None = None

        async def close(self, code: int = 1000):
            self.closed = True
            self.close_code = code

    host_ws = FakeWS()
    viewer_ws1 = FakeWS()
    viewer_ws2 = FakeWS()

    await mgr.register_host("s1", teacher.id, host_ws)  # type: ignore[arg-type]
    room = await mgr.register_viewer("s1", "u1", viewer_ws1)  # type: ignore[arg-type]
    assert room is not None
    assert len(room.viewers) == 1

    # Reconnect with a fresh WS — prior should be closed, count unchanged.
    room2 = await mgr.register_viewer("s1", "u1", viewer_ws2)  # type: ignore[arg-type]
    assert room2 is not None
    assert room2.viewers["u1"] is viewer_ws2
    assert len(room2.viewers) == 1
    assert viewer_ws1.closed is True


async def test_signaling_register_host_replaces_stale_ws(db, teacher):
    """Host reconnect closes the stale host socket without destroying the room."""
    from app.routers.live import SignalingManager

    mgr = SignalingManager()

    class FakeWS:
        def __init__(self):
            self.closed = False

        async def close(self, code: int = 1000):
            self.closed = True

    host1 = FakeWS()
    host2 = FakeWS()
    await mgr.register_host("s1", teacher.id, host1)  # type: ignore[arg-type]
    await mgr.register_host("s1", teacher.id, host2)  # type: ignore[arg-type]
    room = mgr.get("s1")
    assert room is not None
    assert room.host_ws is host2
    assert host1.closed is True
