"""Live Session router — teacher-hosted livestreams.

Endpoints
---------
  POST   /live/start                     — create + start a session (host-only)
  POST   /live/{id}/end                  — end a session (host-only)
  GET    /live/sessions                  — list active sessions for caller's org
  GET    /live/sessions/{id}             — detail
  WS     /live/ws/{session_id}?token=    — WebRTC signaling relay

Signaling relay
---------------
The backend never touches media. It only forwards opaque JSON frames
between the host and the viewers so WebRTC peers can exchange SDP and
ICE candidates through NAT. Frames have shape:

    {"type": "offer"|"answer"|"candidate"|"bye", "target": "<uid|host|all>", ...}

* Host → viewer(s): broadcasts when ``target == "all"``, direct-sends when
  ``target`` is a specific user id.
* Viewer → host: always forwarded to the host only.

A session with no live host socket rejects new viewer connections with
4404 so browsers don't pile up against a dead room.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query,
    UploadFile, File,
)
from jose import JWTError
from sqlalchemy import select, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.features import require_feature
from app.core.plans import UNLIMITED, plan_for, plan_limit_detail
from app.core.security import decode_token
from app.database import get_db, AsyncSessionLocal
from app.deps import get_current_active_user
from app.models.user import User, UserStatus
from app.models.live import LiveSession, LiveRecording, LiveAttendance
from app.models.modules.school import (
    SchoolClass, Student, Subject, Timetable,
    AttendanceRecord, AttendanceStatus,
)
from app.models.organization import Organization
from app.schemas.live import (
    LiveSessionCreate, LiveSessionResponse,
    LiveRecordingResponse, LiveAnalyticsResponse, LiveAttendeeResponse,
    TimetableSlotResponse,
)
from app.services.ice import build_ice_servers
from app.services.usage import track as track_usage

from sqlalchemy import func


ALLOWED_RECORDING_MIMES = {"video/webm", "video/mp4", "audio/webm"}
# Recordings are bigger than messenger media; give them their own cap.
MAX_RECORDING_MB = 500


def _normalise_mime(ctype: str) -> str:
    """Strip parameters so 'video/webm;codecs=vp9,opus' matches 'video/webm'.

    Browsers ship codec hints on the Content-Type header for MediaRecorder
    blobs (vp9/vp8/opus depending on capability). The allow-list is intentionally
    the base type — we don't want to enumerate every codec permutation.
    """
    return (ctype or "").split(";", 1)[0].strip().lower()


logger = logging.getLogger("extracare.live")
router = APIRouter(prefix="/live", tags=["Livestream"])


# ── Signaling manager (in-process) ──────────────────────────────────────────
#
# One entry per active session. Host has a distinguished slot so viewers
# can find it by name instead of passing its user_id everywhere.

class SignalingRoom:
    def __init__(self, host_user_id: str) -> None:
        self.host_user_id = host_user_id
        self.host_ws: Optional[WebSocket] = None
        # user_id → WebSocket (viewers only)
        self.viewers: dict[str, WebSocket] = {}
        # Peak concurrent viewers in this room; read at session end for
        # analytics without needing a separate time-series.
        self.peak_viewer_count: int = 0
        # user_id → muted state so host decisions survive reconnects
        # within the same room lifetime.
        self.muted: set[str] = set()


class SignalingManager:
    def __init__(self) -> None:
        self._rooms: dict[str, SignalingRoom] = {}
        self._lock = asyncio.Lock()

    async def register_host(self, session_id: str, host_id: str, ws: WebSocket) -> None:
        # If a stale host WS is already in place, close it — the new socket wins.
        async with self._lock:
            room = self._rooms.setdefault(session_id, SignalingRoom(host_user_id=host_id))
            prior = room.host_ws
            room.host_ws = ws
        if prior is not None and prior is not ws:
            try:
                await prior.close(code=4409)
            except Exception:
                pass

    async def register_viewer(self, session_id: str, user_id: str, ws: WebSocket) -> Optional[SignalingRoom]:
        # Reconnect-safe: the new WS replaces any prior socket for the same user_id.
        prior: Optional[WebSocket] = None
        async with self._lock:
            room = self._rooms.get(session_id)
            if not room or not room.host_ws:
                return None
            prior = room.viewers.get(user_id)
            room.viewers[user_id] = ws
            if len(room.viewers) > room.peak_viewer_count:
                room.peak_viewer_count = len(room.viewers)
        if prior is not None and prior is not ws:
            try:
                await prior.close(code=4409)
            except Exception:
                pass
        return self._rooms.get(session_id)

    def peak(self, session_id: str) -> int:
        room = self._rooms.get(session_id)
        return room.peak_viewer_count if room else 0

    async def unregister(self, session_id: str, user_id: str, is_host: bool) -> None:
        async with self._lock:
            room = self._rooms.get(session_id)
            if not room:
                return
            if is_host:
                room.host_ws = None
                # Close every viewer so the room doesn't linger with a dead host.
                for vws in list(room.viewers.values()):
                    try:
                        await vws.send_text(json.dumps({"event": "host_left"}))
                        await vws.close()
                    except Exception:
                        pass
                self._rooms.pop(session_id, None)
            else:
                room.viewers.pop(user_id, None)

    def get(self, session_id: str) -> Optional[SignalingRoom]:
        return self._rooms.get(session_id)

    def viewer_count(self, session_id: str) -> int:
        room = self._rooms.get(session_id)
        return len(room.viewers) if room else 0


signaling = SignalingManager()


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _load_session(db: AsyncSession, session_id: str, org_id: str) -> LiveSession:
    row = (await db.execute(
        select(LiveSession).where(
            LiveSession.id == session_id,
            LiveSession.org_id == org_id,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Live session not found: {session_id}")
    return row


async def _is_user_authorised_for_session(
    db: AsyncSession, user: User, session: LiveSession,
) -> bool:
    """Roster gate. Rules:

    - Host is always allowed.
    - Org superadmin / "school:*" permission is always allowed — admins
      supervise live classrooms.
    - If the session has no class_id: any org member may join (back-compat).
    - If class_id is set: allow the class's teacher + enrolled students.
      Enrolment resolves via Student.email == user.email in the same org.
    """
    if user.id == session.host_user_id:
        return True
    if user.is_superadmin:
        # Platform-level admin always sees everything; org-level admins are
        # usually the session's class teacher, which is covered below.
        return True
    if not session.class_id:
        return True  # open to the whole org when no roster binding.

    klass = (await db.execute(
        select(SchoolClass).where(
            SchoolClass.id == session.class_id,
            SchoolClass.org_id == user.org_id,
        )
    )).scalar_one_or_none()
    if not klass:
        # Class was deleted after the session was scoped — deny; host can
        # unlink by creating a new session without class_id.
        return False

    if klass.teacher_id == user.id:
        return True

    if not user.email:
        return False
    student = (await db.execute(
        select(Student.id).where(
            Student.email == user.email,
            Student.org_id == user.org_id,
            Student.class_id == session.class_id,
            Student.is_deleted == False,
            Student.is_active == True,
        )
    )).scalar_one_or_none()
    return student is not None


def _to_response(
    s: LiveSession, viewer_count: int = 0, has_recording: bool = False,
) -> LiveSessionResponse:
    return LiveSessionResponse(
        id=s.id,
        org_id=s.org_id,
        host_user_id=s.host_user_id,
        host_name=(s.host.full_name if s.host else None),
        title=s.title,
        description=s.description,
        class_id=s.class_id,
        subject_id=s.subject_id,
        timetable_id=s.timetable_id,
        is_active=s.is_active,
        started_at=s.started_at,
        ended_at=s.ended_at,
        viewer_count=viewer_count,
        has_recording=has_recording,
        created_at=s.created_at,
    )


async def _mark_class_attendance(
    db: AsyncSession, *, user: User, session: LiveSession, when: datetime,
) -> None:
    """Upsert an AttendanceRecord for (student, class, today) marking the
    student PRESENT because they joined a class-bound live session.

    No-ops when:
      - The user isn't resolvable to a Student row (teachers, admins,
        staff who share the viewer join event — they shouldn't pollute
        the class register).
      - An AttendanceRecord already exists for this (student, class, day)
        — honours manual attendance marking done earlier in the day.
      - The session isn't actually tied to a class the viewer is on.
    """
    if not user.email or not session.class_id:
        return
    student_id = (await db.execute(
        select(Student.id).where(
            Student.email == user.email,
            Student.org_id == user.org_id,
            Student.class_id == session.class_id,
            Student.is_deleted == False,  # noqa: E712
            Student.is_active == True,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not student_id:
        return

    today = when.date()
    existing = (await db.execute(
        select(AttendanceRecord.id).where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.class_id == session.class_id,
            AttendanceRecord.date == today,
        )
    )).scalar_one_or_none()
    if existing:
        return  # Don't overwrite manual registers.

    db.add(AttendanceRecord(
        org_id=user.org_id,
        student_id=student_id,
        class_id=session.class_id,
        date=today,
        status=AttendanceStatus.PRESENT,
        marked_by=None,  # system-marked; distinct from teacher-marked.
        notes=f"Joined live session {session.id}",
    ))


async def _record_viewer_join(
    db: AsyncSession,
    *,
    user: User,
    session: LiveSession,
    now: datetime,
    resume_window_seconds: int = 30,
) -> tuple[str, datetime]:
    """Create or resume the LiveAttendance row for a viewer joining a session.

    Reconnect-safe: if the viewer has an open row (stale WS never closed it)
    or a row that left_at within ``resume_window_seconds``, we reopen that
    row instead of creating a duplicate. Flaky-network students should
    produce one attendance row, not a dozen.

    Returns ``(attendance_id, effective_joined_at)``. When resuming, the
    joined_at returned is the *original* join — that way the disconnect
    handler computes total watch duration, not just the latest segment.
    """
    recent_cutoff = now - timedelta(seconds=resume_window_seconds)
    recent_row = (await db.execute(
        select(LiveAttendance)
        .where(
            LiveAttendance.session_id == session.id,
            LiveAttendance.user_id == user.id,
        )
        .order_by(desc(LiveAttendance.joined_at))
        .limit(1)
    )).scalar_one_or_none()

    resume = False
    if recent_row is not None:
        left = recent_row.left_at
        if left is None:
            resume = True
        else:
            if left.tzinfo is None:
                left = left.replace(tzinfo=timezone.utc)
            if left >= recent_cutoff:
                resume = True

    if resume and recent_row is not None:
        await db.execute(
            update(LiveAttendance)
            .where(LiveAttendance.id == recent_row.id)
            .values(left_at=None, duration_seconds=None)
        )
        stored = recent_row.joined_at
        if stored.tzinfo is None:
            stored = stored.replace(tzinfo=timezone.utc)
        await db.commit()
        return recent_row.id, stored

    att = LiveAttendance(
        org_id=user.org_id,
        session_id=session.id,
        user_id=user.id,
        joined_at=now,
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return att.id, now


async def _recording_flags(db: AsyncSession, session_ids: list[str]) -> set[str]:
    """Batch: return the set of session_ids that have at least one recording."""
    if not session_ids:
        return set()
    rows = (await db.execute(
        select(LiveRecording.session_id)
        .where(LiveRecording.session_id.in_(session_ids))
        .distinct()
    )).scalars().all()
    return set(rows)


def _recording_url(session_id: str, file_path: str) -> str:
    # File is served via the /uploads static mount + a tenant-scoped folder;
    # keep the return URL relative so the frontend's resolveMediaUrl prefixes
    # the API origin (dev) or CDN (prod).
    return f"/uploads/{file_path}"


# ── REST: ICE config ────────────────────────────────────────────────────────

@router.get("/ice-config")
async def ice_config(
    current_user: User = Depends(get_current_active_user),
):
    """Return STUN/TURN servers for the browser's RTCPeerConnection.

    Ephemeral TURN creds are scoped to the calling user id so usage is
    attributable and revocation is possible by rotating TURN_SECRET.
    """
    settings = get_settings()
    return {"iceServers": build_ice_servers(settings, user_id=current_user.id)}


# ── REST: start / end / list ────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=LiveSessionResponse,
    status_code=201,
    dependencies=[Depends(require_feature("livestream"))],
)
async def start_session(
    data: LiveSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Open a new session. Any authenticated user can host; authorisation
    for "only teachers can host" should be layered via role on top."""
    now = datetime.now(timezone.utc)
    session = LiveSession(
        org_id=current_user.org_id,
        host_user_id=current_user.id,
        title=data.title.strip(),
        description=data.description,
        class_id=data.class_id,
        subject_id=data.subject_id,
        timetable_id=data.timetable_id,
        is_active=True,
        started_at=now,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    track_usage(current_user.org_id, "school", "live.session_started")
    logger.info("live.start user=%s org=%s session=%s", current_user.id, current_user.org_id, session.id)
    return _to_response(session, viewer_count=0)


# ── REST: timetable integration ─────────────────────────────────────────────

def _parse_slot_time(hhmm: str) -> tuple[int, int]:
    """Timetable stores "HH:MM" as a string. Return (hour, minute)
    defensively — bad data logs a warning and is treated as 00:00 so the
    endpoint stays resilient rather than 500'ing on a typo."""
    try:
        h, m = hhmm.split(":")
        return int(h), int(m)
    except (ValueError, AttributeError):
        logger.warning("live.timetable.bad-time value=%r", hhmm)
        return 0, 0


def _slot_contains(slot: Timetable, now: datetime) -> bool:
    """Does `now` fall within this slot on its day_of_week?

    Comparison happens in UTC — callers should pre-localise `now` to the
    org's timezone before calling, but we stay UTC-consistent internally.
    """
    if now.weekday() != slot.day_of_week:
        return False
    sh, sm = _parse_slot_time(slot.start_time)
    eh, em = _parse_slot_time(slot.end_time)
    start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    return start <= now <= end


@router.get("/timetable/today", response_model=list[TimetableSlotResponse])
async def timetable_today(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Today's timetable for the caller — teacher view gets slots they
    host; student view gets slots for their enrolled class.

    Each slot carries a `live_session_id` if a matching active session
    already exists (so the frontend can render "Join" vs "Go Live") and
    a `can_host` flag that drives the "Go Live" button visibility.
    """
    now = datetime.now(timezone.utc)
    dow = now.weekday()

    # Figure out which class_ids the caller can see timetables for.
    # Teachers see the ones they teach. Students see their enrolled class.
    # Admins see everything in their org.
    if current_user.is_superadmin:
        class_filter = None
    else:
        teacher_class_ids = (await db.execute(
            select(SchoolClass.id).where(
                SchoolClass.org_id == current_user.org_id,
                SchoolClass.teacher_id == current_user.id,
            )
        )).scalars().all()
        student_class_ids: list[str] = []
        if current_user.email:
            student_class_ids = (await db.execute(
                select(Student.class_id).where(
                    Student.org_id == current_user.org_id,
                    Student.email == current_user.email,
                    Student.class_id.isnot(None),
                    Student.is_deleted == False,  # noqa: E712
                    Student.is_active == True,  # noqa: E712
                )
            )).scalars().all()
        class_filter = list({*teacher_class_ids, *student_class_ids})
        if not class_filter:
            return []

    q = select(Timetable).where(
        Timetable.org_id == current_user.org_id,
        Timetable.day_of_week == dow,
    )
    if class_filter is not None:
        q = q.where(Timetable.class_id.in_(class_filter))
    q = q.order_by(Timetable.start_time.asc())
    slots = (await db.execute(q)).scalars().all()
    if not slots:
        return []

    # Preload class + subject names in two batch queries to avoid N+1.
    class_ids = {s.class_id for s in slots if s.class_id}
    subject_ids = {s.subject_id for s in slots if s.subject_id}
    class_map: dict[str, str] = {}
    subject_map: dict[str, str] = {}
    if class_ids:
        rows = (await db.execute(
            select(SchoolClass.id, SchoolClass.name).where(SchoolClass.id.in_(class_ids))
        )).all()
        class_map = {r[0]: r[1] for r in rows}
    if subject_ids:
        rows = (await db.execute(
            select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
        )).all()
        subject_map = {r[0]: r[1] for r in rows}

    # Map of timetable_id → active live session id (if any). A slot with
    # more than one active session only surfaces the most recent — rare,
    # but possible if a teacher re-launches after a crash.
    session_map: dict[str, str] = {}
    live_rows = (await db.execute(
        select(LiveSession.id, LiveSession.timetable_id)
        .where(
            LiveSession.org_id == current_user.org_id,
            LiveSession.is_active == True,  # noqa: E712
            LiveSession.timetable_id.in_([s.id for s in slots]),
        )
        .order_by(desc(LiveSession.started_at))
    )).all()
    for sid, tid in live_rows:
        session_map.setdefault(tid, sid)

    out: list[TimetableSlotResponse] = []
    for slot in slots:
        can_host = (
            current_user.is_superadmin
            or slot.teacher_id == current_user.id
        )
        out.append(TimetableSlotResponse(
            timetable_id=slot.id,
            class_id=slot.class_id,
            class_name=class_map.get(slot.class_id),
            subject_id=slot.subject_id,
            subject_name=subject_map.get(slot.subject_id) if slot.subject_id else None,
            day_of_week=slot.day_of_week,
            start_time=slot.start_time,
            end_time=slot.end_time,
            is_current=_slot_contains(slot, now),
            live_session_id=session_map.get(slot.id),
            can_host=can_host,
        ))
    return out


@router.post(
    "/from-timetable/{timetable_id}",
    response_model=LiveSessionResponse,
    status_code=201,
    dependencies=[Depends(require_feature("livestream"))],
)
async def start_from_timetable(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """One-click "Go Live" from a timetable slot. Creates a class-bound
    session scoped to the slot's class + subject, or returns the existing
    active session if one is already live for this slot (idempotent).

    Only the slot's assigned teacher (or an admin) can host.
    """
    slot = (await db.execute(
        select(Timetable).where(
            Timetable.id == timetable_id,
            Timetable.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail=f"Timetable slot not found: {timetable_id}")

    if not current_user.is_superadmin and slot.teacher_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the class's assigned teacher can start this session.",
        )

    # Idempotent: if a session is already active for this slot, return it.
    existing = (await db.execute(
        select(LiveSession).where(
            LiveSession.org_id == current_user.org_id,
            LiveSession.timetable_id == slot.id,
            LiveSession.is_active == True,  # noqa: E712
        )
        .order_by(desc(LiveSession.started_at))
        .limit(1)
    )).scalar_one_or_none()
    if existing:
        return _to_response(existing, viewer_count=signaling.viewer_count(existing.id))

    klass_name = (await db.execute(
        select(SchoolClass.name).where(SchoolClass.id == slot.class_id)
    )).scalar_one_or_none()
    subj_name = None
    if slot.subject_id:
        subj_name = (await db.execute(
            select(Subject.name).where(Subject.id == slot.subject_id)
        )).scalar_one_or_none()

    # Title uses what the teacher would have typed: "Year 10 — Maths".
    title_bits = [b for b in (klass_name, subj_name) if b]
    title = " — ".join(title_bits) if title_bits else "Live lesson"

    now = datetime.now(timezone.utc)
    session = LiveSession(
        org_id=current_user.org_id,
        host_user_id=current_user.id,
        title=title,
        class_id=slot.class_id,
        subject_id=slot.subject_id,
        timetable_id=slot.id,
        is_active=True,
        started_at=now,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    track_usage(current_user.org_id, "school", "live.session_started")
    logger.info(
        "live.from-timetable user=%s slot=%s session=%s",
        current_user.id, slot.id, session.id,
    )
    return _to_response(session, viewer_count=0)


@router.post("/{session_id}/end", response_model=LiveSessionResponse)
async def end_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    session = await _load_session(db, session_id, current_user.org_id)
    if session.host_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the host can end this session.")
    if session.is_active:
        session.is_active = False
        session.ended_at = datetime.now(timezone.utc)
        # Billing input: stream-minutes are billed per-session, so emit
        # once at end time rather than sampling every minute.
        if session.started_at:
            # SQLite (test backend) returns naive datetimes even when the
            # column is DateTime(timezone=True). Normalise before diffing.
            started = session.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            minutes = max(
                0,
                int((session.ended_at - started).total_seconds() // 60),
            )
            if minutes:
                track_usage(current_user.org_id, "school", "live.stream_minutes", minutes)
        await db.flush()
    # Tear down the signaling room so lingering viewers get kicked.
    await signaling.unregister(session.id, current_user.id, is_host=True)
    return _to_response(session, viewer_count=0)


@router.get("/sessions", response_model=list[LiveSessionResponse])
async def list_sessions(
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(LiveSession).where(LiveSession.org_id == current_user.org_id)
    if active_only:
        q = q.where(LiveSession.is_active == True)
    q = q.order_by(desc(LiveSession.started_at)).limit(50)
    rows = (await db.execute(q)).scalars().all()
    # Hide class-bound sessions the caller isn't on the roster for, so
    # other students don't see "Year 10 Maths" in their sidebar.
    visible: list[LiveSession] = []
    for s in rows:
        if await _is_user_authorised_for_session(db, current_user, s):
            visible.append(s)
    with_rec = await _recording_flags(db, [s.id for s in visible])
    return [
        _to_response(
            s,
            viewer_count=signaling.viewer_count(s.id),
            has_recording=s.id in with_rec,
        )
        for s in visible
    ]


@router.get("/sessions/{session_id}", response_model=LiveSessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    session = await _load_session(db, session_id, current_user.org_id)
    if not await _is_user_authorised_for_session(db, current_user, session):
        # Mirror tenant-isolation behaviour: don't leak existence.
        raise HTTPException(status_code=404, detail=f"Live session not found: {session_id}")
    with_rec = await _recording_flags(db, [session.id])
    return _to_response(
        session,
        viewer_count=signaling.viewer_count(session.id),
        has_recording=session.id in with_rec,
    )


# ── REST: recordings ────────────────────────────────────────────────────────

@router.post(
    "/{session_id}/recording",
    response_model=LiveRecordingResponse,
    status_code=201,
    dependencies=[Depends(require_feature("livestream"))],
)
async def upload_recording(
    session_id: str,
    file: UploadFile = File(...),
    duration_seconds: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Host uploads the recorded blob from their browser MediaRecorder.

    We don't record on the server because WebRTC peers are routed through
    the host's browser (no SFU). The host captures `localStream` via
    MediaRecorder and posts the blob here when the session ends.
    """
    settings = get_settings()
    session = await _load_session(db, session_id, current_user.org_id)
    if session.host_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the host can upload recordings.")

    raw_ctype = (file.content_type or "").lower()
    base_ctype = _normalise_mime(raw_ctype)
    if base_ctype not in ALLOWED_RECORDING_MIMES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported recording format: {raw_ctype or 'unknown'}",
        )
    # Store the codec-stripped type so downstream consumers (playback,
    # analytics) get a clean value without branching on codec suffixes.
    ctype = base_ctype

    # Plan-level storage quota. We sum the org's existing recording bytes
    # up-front so the frontend gets a precise 402 before the user spends
    # bandwidth uploading a blob we'd just reject.
    org = (await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )).scalar_one_or_none()
    plan = plan_for(org.subscription_tier if org else None)
    if plan.recording_storage_mb != UNLIMITED:
        used_bytes = (await db.execute(
            select(func.coalesce(func.sum(LiveRecording.file_size), 0))
            .where(LiveRecording.org_id == current_user.org_id)
        )).scalar() or 0
        quota_bytes = plan.recording_storage_mb * 1024 * 1024
        if used_bytes >= quota_bytes:
            raise HTTPException(
                status_code=402,
                detail=plan_limit_detail(
                    reason="recording_storage_exceeded",
                    current_plan=plan.tier,
                ),
            )
        # Cap this upload so we never exceed the quota mid-file. Use the
        # smaller of the plan's remaining headroom and the per-file cap.
        max_bytes = min(
            MAX_RECORDING_MB * 1024 * 1024,
            quota_bytes - used_bytes,
        )
    else:
        max_bytes = MAX_RECORDING_MB * 1024 * 1024
    # Tenant + session nested folder so recordings never cross boundaries
    # and cleanup-by-session is a single rmdir.
    sess_dir = Path(settings.UPLOAD_DIR) / current_user.org_id / "live" / session.id
    sess_dir.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(file.filename or "recording.webm")[1].lower() or ".webm"
    fname = f"{uuid.uuid4().hex}{ext}"
    path = sess_dir / fname

    size = 0
    with open(path, "wb") as out:
        while True:
            chunk = await file.read(1024 * 64)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                out.close()
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=413,
                    detail=f"Recording exceeds {MAX_RECORDING_MB}MB cap.",
                )
            out.write(chunk)

    # Store the path relative to UPLOAD_DIR so it works against any mount.
    rel_path = f"{current_user.org_id}/live/{session.id}/{fname}"
    rec = LiveRecording(
        org_id=current_user.org_id,
        session_id=session.id,
        file_path=rel_path,
        file_size=size,
        duration_seconds=duration_seconds,
        mime_type=ctype,
        created_by=current_user.id,
    )
    db.add(rec)
    await db.flush()
    await db.refresh(rec)
    # Usage grain is MB, rounded up, so a 1-byte file still costs 1 unit.
    # Matches how Paystack et al. bill for storage tiers.
    mb = max(1, (size + 1024 * 1024 - 1) // (1024 * 1024)) if size else 0
    if mb:
        track_usage(current_user.org_id, "school", "live.recording_mb", mb)
    logger.info("live.recording.upload session=%s size=%d", session.id, size)

    return LiveRecordingResponse(
        id=rec.id,
        session_id=rec.session_id,
        file_url=_recording_url(rec.session_id, rec.file_path),
        file_size=rec.file_size,
        duration_seconds=rec.duration_seconds,
        mime_type=rec.mime_type,
        created_at=rec.created_at,
    )


@router.get("/{session_id}/recordings", response_model=list[LiveRecordingResponse])
async def list_recordings(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    session = await _load_session(db, session_id, current_user.org_id)
    if not await _is_user_authorised_for_session(db, current_user, session):
        raise HTTPException(status_code=404, detail=f"Live session not found: {session_id}")
    rows = (await db.execute(
        select(LiveRecording)
        .where(LiveRecording.session_id == session.id)
        .order_by(desc(LiveRecording.created_at))
    )).scalars().all()
    return [
        LiveRecordingResponse(
            id=r.id,
            session_id=r.session_id,
            file_url=_recording_url(r.session_id, r.file_path),
            file_size=r.file_size,
            duration_seconds=r.duration_seconds,
            mime_type=r.mime_type,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ── REST: analytics ─────────────────────────────────────────────────────────

@router.get("/{session_id}/analytics", response_model=LiveAnalyticsResponse)
async def session_analytics(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Attendance analytics — host-only.

    Teachers need to know who watched and for how long. We compute this
    from LiveAttendance rows written by the signaling WS, so offline
    replays (no WS) don't pollute the numbers.
    """
    session = await _load_session(db, session_id, current_user.org_id)
    if session.host_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the host can view analytics.")

    rows = (await db.execute(
        select(LiveAttendance, User.full_name)
        .join(User, User.id == LiveAttendance.user_id, isouter=True)
        .where(LiveAttendance.session_id == session.id)
        .order_by(LiveAttendance.joined_at.asc())
    )).all()

    attendees = [
        LiveAttendeeResponse(
            user_id=r.LiveAttendance.user_id,
            user_name=r.full_name,
            joined_at=r.LiveAttendance.joined_at,
            left_at=r.LiveAttendance.left_at,
            duration_seconds=r.LiveAttendance.duration_seconds,
        )
        for r in rows
    ]

    total_joins = len(attendees)
    unique_viewers = len({a.user_id for a in attendees})
    completed = [a.duration_seconds for a in attendees if a.duration_seconds is not None]
    avg_watch = int(sum(completed) / len(completed)) if completed else None

    return LiveAnalyticsResponse(
        session_id=session.id,
        total_joins=total_joins,
        unique_viewers=unique_viewers,
        current_viewer_count=signaling.viewer_count(session.id),
        peak_viewer_count=signaling.peak(session.id),
        average_watch_seconds=avg_watch,
        attendees=attendees,
    )


# ── WebSocket signaling ─────────────────────────────────────────────────────

async def _auth_ws(token: str) -> Optional[User]:
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        uid = payload.get("sub")
        if not uid:
            return None
    except JWTError:
        return None

    async with AsyncSessionLocal() as db:
        user = (await db.execute(
            select(User).where(User.id == uid, User.is_deleted == False)
        )).scalar_one_or_none()
        if not user or user.status != UserStatus.ACTIVE:
            return None
        return user


@router.websocket("/ws/{session_id}")
async def live_ws(
    ws: WebSocket,
    session_id: str,
    token: str | None = Query(default=None, description="JWT access token (Bearer clients); cookie clients omit it."),
):
    """Signaling channel. The host registers first; viewers then connect
    and exchange SDP/ICE with the host through relayed frames."""
    # Cookie-auth clients rely on the access_token cookie on the WS handshake.
    user = await _auth_ws(token or ws.cookies.get("access_token"))
    if not user:
        await ws.close(code=4401)
        return

    # Authorise: the session must exist, belong to the caller's org, and
    # (when bound to a class) the caller must be on the roster.
    async with AsyncSessionLocal() as db:
        session = (await db.execute(
            select(LiveSession).where(
                LiveSession.id == session_id,
                LiveSession.org_id == user.org_id,
                LiveSession.is_active == True,
            )
        )).scalar_one_or_none()
        if not session:
            await ws.close(code=4404)
            return
        if not await _is_user_authorised_for_session(db, user, session):
            # 4403 = policy failure, distinct from "no such room".
            await ws.close(code=4403)
            return

    is_host = user.id == session.host_user_id
    await ws.accept()

    attendance_id: Optional[str] = None
    joined_at: Optional[datetime] = None

    if is_host:
        await signaling.register_host(session.id, user.id, ws)
    else:
        room = await signaling.register_viewer(session.id, user.id, ws)
        if not room:
            # Host hasn't joined yet (or dropped) — refuse rather than
            # wait, so the viewer's UI can render a clear "offline" state.
            await ws.send_text(json.dumps({"event": "error", "detail": "host_offline"}))
            await ws.close(code=4404)
            return
        # Record the join for analytics. Reconnect-aware: if the viewer has
        # an open row (stale WS left it un-closed) or a recently closed row
        # (<30s ago) we resume it instead of stacking duplicates. See
        # `_record_viewer_join` for the dedup rules.
        async with AsyncSessionLocal() as adb:
            attendance_id, joined_at = await _record_viewer_join(
                adb, user=user, session=session, now=datetime.now(timezone.utc),
            )
            # ERP bridge: for class-bound sessions, mirror the viewer join
            # into AttendanceRecord so the class register reflects online
            # presence too. Idempotent per (student, class, date) — a
            # student who joins twice in a day doesn't stack up rows.
            if session.class_id:
                try:
                    await _mark_class_attendance(
                        adb, user=user, session=session, when=joined_at,
                    )
                    await adb.commit()
                except Exception:
                    logger.exception(
                        "live.attendance.class-bridge failed session=%s user=%s",
                        session.id, user.id,
                    )

        # Announce to the host so they can kick off the offer.
        try:
            await room.host_ws.send_text(json.dumps({
                "event": "viewer_joined",
                "user_id": user.id,
                "name": user.full_name,
            }))
        except Exception:
            pass

    await ws.send_text(json.dumps({
        "event": "connected",
        "role": "host" if is_host else "viewer",
        "session_id": session.id,
    }))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            room = signaling.get(session.id)
            if not room:
                break

            # Stamp the sender so the recipient can route responses back.
            payload["from"] = user.id

            if is_host:
                # Host → viewer(s). ``target`` can be a specific viewer id
                # or "all" for fan-out (e.g. announcements).
                target = payload.get("target")
                if target == "all" or target is None:
                    for vws in list(room.viewers.values()):
                        try:
                            await vws.send_text(json.dumps(payload))
                        except Exception:
                            pass
                else:
                    vws = room.viewers.get(target)
                    if vws:
                        try:
                            await vws.send_text(json.dumps(payload))
                        except Exception:
                            pass
            else:
                # Viewer → host, always.
                if room.host_ws:
                    try:
                        await room.host_ws.send_text(json.dumps(payload))
                    except Exception:
                        pass
    except WebSocketDisconnect:
        pass
    finally:
        await signaling.unregister(session.id, user.id, is_host=is_host)
        # Close out the attendance row so durations are available to the
        # analytics endpoint. Failures here aren't user-visible.
        if attendance_id and joined_at:
            left_at = datetime.now(timezone.utc)
            duration = int((left_at - joined_at).total_seconds())
            try:
                async with AsyncSessionLocal() as adb:
                    await adb.execute(
                        update(LiveAttendance)
                        .where(LiveAttendance.id == attendance_id)
                        .values(left_at=left_at, duration_seconds=duration)
                    )
                    await adb.commit()
            except Exception:
                logger.exception("live.attendance.close-failed session=%s user=%s", session.id, user.id)
        logger.info(
            "live.ws.disconnect user=%s session=%s role=%s",
            user.id, session.id, "host" if is_host else "viewer",
        )
