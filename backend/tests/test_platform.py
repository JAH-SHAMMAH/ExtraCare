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
from app.models.modules.platform import UnmappedPunch
from app.routers.modules.biometric import (
    register_device, create_enrollment, ingest_punches, list_quarantine, resolve_punch,
)
from app.routers.modules.platform import (
    create_poll, cast_vote, create_house, send_message, my_inbox, mark_read,
)
from app.schemas.platform import (
    DeviceCreate, EnrollmentCreate, IngestPunchesRequest, PunchIn, ResolvePunchRequest,
    PollCreate, CastVote, HouseCreate, MessageCreate,
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


# ── Biometric: idempotency on the device record id ───────────────────────────────

async def test_ingest_dedupes_on_record_id_not_timestamp(db, org, student):
    admin = await _admin(db, org)
    await register_device(DeviceCreate(device_id="DEV1", name="Gate"), db=db, current_user=admin)
    await create_enrollment(EnrollmentCreate(biometric_user_id="U100", student_id=student.id), db=db, current_user=admin)

    t = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
    punch = PunchIn(device_id="DEV1", biometric_user_id="U100", event_time=t, direction="check_in", record_id="REC-1")
    r1 = await ingest_punches(IngestPunchesRequest(punches=[punch]), db=db, current_user=admin)
    assert r1.ingested == 1 and r1.duplicates == 0
    # Re-push the SAME record id but with a DRIFTED timestamp → still a duplicate.
    drifted = PunchIn(device_id="DEV1", biometric_user_id="U100", event_time=t + timedelta(minutes=3), direction="check_in", record_id="REC-1")
    r2 = await ingest_punches(IngestPunchesRequest(punches=[drifted]), db=db, current_user=admin)
    assert r2.ingested == 0 and r2.duplicates == 1
    # Exactly one attendance event exists for that punch.
    evs = [e for e in await _events(db, org) if e.external_ref == "REC-1"]
    assert len(evs) == 1


async def test_clock_skew_is_surfaced(db, org, student):
    from app.routers.modules.biometric import list_devices
    admin = await _admin(db, org)
    await register_device(DeviceCreate(device_id="DEV2", name="Side"), db=db, current_user=admin)
    await create_enrollment(EnrollmentCreate(biometric_user_id="U200", student_id=student.id), db=db, current_user=admin)
    old = datetime.now(timezone.utc) - timedelta(minutes=20)
    await ingest_punches(IngestPunchesRequest(punches=[PunchIn(device_id="DEV2", biometric_user_id="U200", event_time=old, record_id="R2")]), db=db, current_user=admin)
    dev = next(d for d in await list_devices(db=db, current_user=admin) if d.device_id == "DEV2")
    assert dev.clock_skew_seconds is not None and dev.clock_skew_seconds > 60   # drift visible, not hidden


# ── Biometric: unmapped punches quarantine + resolve→replay ──────────────────────

async def test_unknown_device_and_unknown_id_quarantine(db, org, student):
    admin = await _admin(db, org)
    await register_device(DeviceCreate(device_id="DEVK", name="Known"), db=db, current_user=admin)
    # unknown device
    r = await ingest_punches(IngestPunchesRequest(punches=[
        PunchIn(device_id="GHOST", biometric_user_id="U1", record_id="A"),
        PunchIn(device_id="DEVK", biometric_user_id="UNMAPPED", record_id="B"),   # unknown biometric id
    ]), db=db, current_user=admin)
    assert r.ingested == 0 and r.quarantined == 2
    assert len(await _events(db, org)) == 0   # nothing posted, no phantom student
    q = await list_quarantine(status="pending", db=db, current_user=admin)
    reasons = {p.reason for p in q}
    assert reasons == {"unknown_device", "unknown_biometric_id"}


async def test_resolve_replays_exactly_one_event(db, org, student):
    admin = await _admin(db, org)
    await register_device(DeviceCreate(device_id="DEVR", name="R"), db=db, current_user=admin)
    await ingest_punches(IngestPunchesRequest(punches=[PunchIn(device_id="DEVR", biometric_user_id="NEW", record_id="RR1", direction="check_in")]), db=db, current_user=admin)
    q = await list_quarantine(status="pending", db=db, current_user=admin)
    punch_id = q[0].id
    res = await resolve_punch(punch_id, ResolvePunchRequest(student_id=student.id, enroll=True), db=db, current_user=admin)
    assert res.ingested == 1
    # The quarantined row is resolved (not deleted) and exactly one event now exists.
    row = (await db.execute(select(UnmappedPunch).where(UnmappedPunch.id == punch_id))).scalar_one()
    assert row.status == "resolved" and row.resolved_event_id is not None
    assert len([e for e in await _events(db, org) if e.external_ref == "RR1"]) == 1


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


# ── RBAC: platform config is admin-only (settings:*) ─────────────────────────────

async def test_platform_rbac_settings_only(db, org):
    admin = await _preset(db, org, "org_admin")
    assert admin.has_permission("settings:write")
    for slug in ("manager", "teacher", "staff", "student", "parent"):
        u = await _preset(db, org, slug)
        assert not u.has_permission("settings:write"), f"{slug} must not hold settings:write"


async def _preset(db, org, slug) -> User:
    return await _user(db, org, SCHOOL_PERMISSION_PRESETS[slug])
