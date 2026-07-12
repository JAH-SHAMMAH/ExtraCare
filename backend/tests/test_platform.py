"""Tests for Administration & Platform (Batch 7).

Biometric (the fiddly one) proves the two things pinned in the design note:
  • idempotency keys on the DEVICE RECORD ID, not the timestamp — a re-push (even
    after a clock-drift correction) ingests ONCE; clock skew is surfaced, not trusted;
  • an unknown device / biometric id QUARANTINES (never dropped, no phantom student)
    and resolve→replay creates exactly one attendance event.
Voting proves one-vote-per-voter (DB-enforced) with derived results. Plus the
other features' CRUD + RBAC (settings:* = admin only).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import AttendanceEvent
from app.models.modules.platform import UnmappedPunch, BiometricDevice
from app.routers.modules.biometric import (
    register_device, create_enrollment, ingest_punches, list_quarantine, resolve_punch,
    issue_device_token, revoke_device_token, authenticate_device,
)
from app.routers.modules.platform import (
    create_poll, cast_vote, create_house, send_message, my_inbox, mark_read,
    create_session, update_session, current_session, list_sessions,
)
from app.schemas.platform import (
    DeviceCreate, EnrollmentCreate, IngestPunchesRequest, PunchIn, ResolvePunchRequest,
    PollCreate, CastVote, HouseCreate, MessageCreate,
    SessionCreate, SessionUpdate,
)


pytestmark = pytest.mark.asyncio


async def _user(db, org, perms: list[str]) -> User:
    u = User(id=str(uuid.uuid4()), email=f"u-{uuid.uuid4().hex[:6]}@example.com", full_name="U", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="r", slug=f"r-{uuid.uuid4().hex[:6]}", permissions=list(perms), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _admin(db, org) -> User:
    return await _user(db, org, ["settings:read", "settings:write"])


async def _events(db, org):
    return (await db.execute(select(AttendanceEvent).where(AttendanceEvent.org_id == org.id))).scalars().all()


async def _device_with_token(db, org, admin, device_id, name="Gate"):
    """Register a device + issue its ingest token; return (device_orm, token).
    Ingest now authenticates by device token, so tests resolve the ORM device."""
    resp = await register_device(DeviceCreate(device_id=device_id, name=name), db=db, current_user=admin)
    tok = await issue_device_token(resp.id, db=db, current_user=admin)
    dev = (await db.execute(select(BiometricDevice).where(BiometricDevice.id == resp.id))).scalar_one()
    return dev, tok.token


# ── Biometric: idempotency on the device record id ───────────────────────────────

async def test_ingest_dedupes_on_record_id_not_timestamp(db, org, student):
    admin = await _admin(db, org)
    dev, _ = await _device_with_token(db, org, admin, "DEV1", "Gate")
    await create_enrollment(EnrollmentCreate(biometric_user_id="U100", student_id=student.id), db=db, current_user=admin)

    t = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
    punch = PunchIn(device_id="DEV1", biometric_user_id="U100", event_time=t, direction="check_in", record_id="REC-1")
    r1 = await ingest_punches(IngestPunchesRequest(punches=[punch]), db=db, device=dev)
    assert r1.ingested == 1 and r1.duplicates == 0
    # Re-push the SAME record id but with a DRIFTED timestamp → still a duplicate.
    drifted = PunchIn(device_id="DEV1", biometric_user_id="U100", event_time=t + timedelta(minutes=3), direction="check_in", record_id="REC-1")
    r2 = await ingest_punches(IngestPunchesRequest(punches=[drifted]), db=db, device=dev)
    assert r2.ingested == 0 and r2.duplicates == 1
    # Exactly one attendance event exists for that punch.
    evs = [e for e in await _events(db, org) if e.external_ref == "REC-1"]
    assert len(evs) == 1


async def test_clock_skew_is_surfaced(db, org, student):
    from app.routers.modules.biometric import list_devices
    admin = await _admin(db, org)
    dev_orm, _ = await _device_with_token(db, org, admin, "DEV2", "Side")
    await create_enrollment(EnrollmentCreate(biometric_user_id="U200", student_id=student.id), db=db, current_user=admin)
    old = datetime.now(timezone.utc) - timedelta(minutes=20)
    await ingest_punches(IngestPunchesRequest(punches=[PunchIn(device_id="DEV2", biometric_user_id="U200", event_time=old, record_id="R2")]), db=db, device=dev_orm)
    dev = next(d for d in await list_devices(db=db, current_user=admin) if d.device_id == "DEV2")
    assert dev.clock_skew_seconds is not None and dev.clock_skew_seconds > 60   # drift visible, not hidden


# ── Biometric: unmapped punches quarantine + resolve→replay ──────────────────────

async def test_unknown_device_and_unknown_id_quarantine(db, org, student):
    admin = await _admin(db, org)
    devk, _ = await _device_with_token(db, org, admin, "DEVK", "Known")
    # unknown device
    r = await ingest_punches(IngestPunchesRequest(punches=[
        PunchIn(device_id="GHOST", biometric_user_id="U1", record_id="A"),
        PunchIn(device_id="DEVK", biometric_user_id="UNMAPPED", record_id="B"),   # unknown biometric id
    ]), db=db, device=devk)
    assert r.ingested == 0 and r.quarantined == 2
    assert len(await _events(db, org)) == 0   # nothing posted, no phantom student
    q = await list_quarantine(status="pending", db=db, current_user=admin)
    reasons = {p.reason for p in q}
    assert reasons == {"unknown_device", "unknown_biometric_id"}


async def test_resolve_replays_exactly_one_event(db, org, student):
    admin = await _admin(db, org)
    devr, _ = await _device_with_token(db, org, admin, "DEVR", "R")
    await ingest_punches(IngestPunchesRequest(punches=[PunchIn(device_id="DEVR", biometric_user_id="NEW", record_id="RR1", direction="check_in")]), db=db, device=devr)
    q = await list_quarantine(status="pending", db=db, current_user=admin)
    punch_id = q[0].id
    res = await resolve_punch(punch_id, ResolvePunchRequest(student_id=student.id, enroll=True), db=db, current_user=admin)
    assert res.ingested == 1
    # The quarantined row is resolved (not deleted) and exactly one event now exists.
    row = (await db.execute(select(UnmappedPunch).where(UnmappedPunch.id == punch_id))).scalar_one()
    assert row.status == "resolved" and row.resolved_event_id is not None
    assert len([e for e in await _events(db, org) if e.external_ref == "RR1"]) == 1


# ── Biometric: per-device ingest token (RELEASE BLOCKER close) ────────────────────

async def test_ingest_requires_valid_device_token(db, org):
    admin = await _admin(db, org)
    dev, token = await _device_with_token(db, org, admin, "DEVT", "Tok")
    # No header → 401 (a general admin session can no longer reach ingest).
    with pytest.raises(HTTPException) as e1:
        await authenticate_device(x_device_token=None, db=db)
    assert e1.value.status_code == 401
    # Wrong token → 401.
    with pytest.raises(HTTPException) as e2:
        await authenticate_device(x_device_token="bio_not_a_real_token", db=db)
    assert e2.value.status_code == 401
    # Valid token → resolves the owning device (and thus its org).
    resolved = await authenticate_device(x_device_token=token, db=db)
    assert resolved.id == dev.id and resolved.org_id == org.id


async def test_device_token_rotate_and_revoke(db, org):
    from app.routers.modules.biometric import list_devices
    admin = await _admin(db, org)
    resp = await register_device(DeviceCreate(device_id="DEVX", name="X"), db=db, current_user=admin)
    # Freshly registered device has no token yet.
    d0 = next(d for d in await list_devices(db=db, current_user=admin) if d.id == resp.id)
    assert d0.has_token is False

    # Issue → plaintext returned once, prefixed; only the hash is stored.
    t1 = await issue_device_token(resp.id, db=db, current_user=admin)
    assert t1.token.startswith("bio_") and t1.token.startswith(t1.token_prefix)
    d1 = next(d for d in await list_devices(db=db, current_user=admin) if d.id == resp.id)
    assert d1.has_token is True and d1.token_prefix == t1.token_prefix
    old_token = t1.token

    # Rotate → the OLD token stops authenticating; the new one works.
    t2 = await issue_device_token(resp.id, db=db, current_user=admin)
    assert t2.token != old_token
    with pytest.raises(HTTPException):
        await authenticate_device(x_device_token=old_token, db=db)
    assert (await authenticate_device(x_device_token=t2.token, db=db)).id == resp.id

    # Revoke → even the current token stops working; has_token flips False.
    await revoke_device_token(resp.id, db=db, current_user=admin)
    with pytest.raises(HTTPException):
        await authenticate_device(x_device_token=t2.token, db=db)
    d2 = next(d for d in await list_devices(db=db, current_user=admin) if d.id == resp.id)
    assert d2.has_token is False


# ── Voting: one vote per voter, derived results ──────────────────────────────────

async def test_one_vote_per_voter_and_derived_results(db, org):
    admin = await _admin(db, org)
    poll = await create_poll(PollCreate(title="Head Boy", options=["Ada", "Bem"]), db=db, current_user=admin)
    opt_a = poll.options[0].id
    voter = await _user(db, org, ["school:reports:read"])   # any member can vote
    after = await cast_vote(poll.id, CastVote(option_id=opt_a), db=db, current_user=voter)
    assert after.total_votes == 1
    assert next(o.votes for o in after.options if o.id == opt_a) == 1
    assert after.my_vote_option_id == opt_a
    # Same voter voting again → hard 409 (DB unique constraint).
    with pytest.raises(HTTPException) as exc:
        await cast_vote(poll.id, CastVote(option_id=poll.options[1].id), db=db, current_user=voter)
    assert exc.value.status_code == 409


# ── Mailbox (announcements) ──────────────────────────────────────────────────────

async def test_mailbox_send_and_inbox(db, org, teacher):
    admin = await _admin(db, org)
    m = await send_message(MessageCreate(subject="Memo", body="Please note", recipient_ids=[teacher.id]), db=db, current_user=admin)
    assert m.recipient_count == 1
    inbox = await my_inbox(db=db, current_user=teacher)
    assert len(inbox) == 1 and inbox[0].subject == "Memo" and inbox[0].read_at is None
    await mark_read(inbox[0].recipient_row_id, db=db, current_user=teacher)
    inbox2 = await my_inbox(db=db, current_user=teacher)
    assert inbox2[0].read_at is not None


# ── Academic sessions: current-term resolver + editable single-current ───────────

async def test_current_session_resolver(db, org):
    admin = await _preset(db, org, "org_admin")
    # nothing current → all null
    empty = await current_session(db=db, current_user=admin)
    assert empty.term is None and empty.name is None and empty.session is None

    await create_session(SessionCreate(name="2025/2026", term="Term 1", is_current=True), db=db, current_user=admin)
    cur = await current_session(db=db, current_user=admin)
    assert cur.term == "Term 1" and cur.name == "2025/2026" and cur.session.is_current is True


async def test_patch_session_is_single_current(db, org):
    admin = await _preset(db, org, "org_admin")
    s1 = await create_session(SessionCreate(name="2025/2026", term="Term 1", is_current=True), db=db, current_user=admin)
    s2 = await create_session(SessionCreate(name="2025/2026", term="Term 2"), db=db, current_user=admin)

    # promote Term 2 → Term 1 must drop out of "current"
    updated = await update_session(s2.id, SessionUpdate(is_current=True), db=db, current_user=admin)
    assert updated.is_current is True
    rows = {s.id: s for s in await list_sessions(db=db, current_user=admin)}
    assert rows[s1.id].is_current is False and rows[s2.id].is_current is True
    assert (await current_session(db=db, current_user=admin)).term == "Term 2"


async def test_patch_session_edits_fields(db, org):
    admin = await _preset(db, org, "org_admin")
    s = await create_session(SessionCreate(name="2025/2026", term="Term 1"), db=db, current_user=admin)
    updated = await update_session(s.id, SessionUpdate(term="Term 3", name="2026/2027"), db=db, current_user=admin)
    assert updated.term == "Term 3" and updated.name == "2026/2027"

    with pytest.raises(HTTPException) as ei:
        await update_session("missing", SessionUpdate(term="Term 1"), db=db, current_user=admin)
    assert ei.value.status_code == 404


async def test_current_session_read_scope_is_broad(db, org):
    # The resolver is read by term-consuming forms: teachers hold school:read but
    # NOT settings:read, so gating it at school:read (not settings:read) is what
    # lets them default from it while session management stays settings:write.
    teacher = await _preset(db, org, "teacher")
    assert teacher.has_permission("school:read") and not teacher.has_permission("settings:read")


# ── RBAC: platform config is admin-only (settings:*) ─────────────────────────────

async def test_platform_rbac_settings_only(db, org):
    admin = await _preset(db, org, "org_admin")
    assert admin.has_permission("settings:write")
    for slug in ("manager", "teacher", "staff", "student", "parent"):
        u = await _preset(db, org, slug)
        assert not u.has_permission("settings:write"), f"{slug} must not hold settings:write"


async def _preset(db, org, slug) -> User:
    return await _user(db, org, SCHOOL_PERMISSION_PRESETS[slug])
