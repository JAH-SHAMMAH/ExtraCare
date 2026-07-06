"""Administration & Platform router (Batch 7), prefix ``/platform``.

School Setup, Custom Fields, Voting, Mailbox (announcements), Mobile Manager.
Admin config is ``settings:*``; per-user surfaces (mailbox inbox, registering a
mobile device, reading app config) are authenticated-only so end users can use
them. Voting integrity: one vote per (poll, voter) is DB-enforced and results
are derived from votes, never a mutable tally.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_module
from app.core.permissions import PermissionChecker
from app.models.user import User, UserStatus
from app.models.modules.platform import (
    AcademicSession, SchoolHouse, GradingBand,
    CustomFieldDefinition, CustomFieldValue,
    Poll, PollOption, PollVote,
    MailboxMessage, MailboxRecipient,
    MobileDevice, MobileAppConfig,
)
from app.schemas.platform import (
    SessionCreate, SessionResponse, HouseCreate, HouseResponse, BandCreate, BandResponse,
    FieldDefCreate, FieldDefResponse, FieldValueSet, FieldValueResponse,
    PollCreate, PollResponse, PollOptionResult, PollListResponse, CastVote,
    MessageCreate, MessageResponse, InboxItemResponse,
    MobileDeviceRegister, MobileDeviceResponse, AppConfigSet, AppConfigResponse,
)
from app.services.ledger import money  # Decimal helper for grading bands

router = APIRouter(prefix="/platform", tags=["Administration & Platform"], dependencies=[Depends(require_module("school"))])

_read = Depends(PermissionChecker("settings:read"))
_write = Depends(PermissionChecker("settings:write"))


# ── School Setup ────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[SessionResponse], dependencies=[_read])
async def list_sessions(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(AcademicSession).where(AcademicSession.org_id == current_user.org_id).order_by(AcademicSession.start_date.desc()))).scalars().all()
    return [SessionResponse(id=s.id, name=s.name, term=s.term, start_date=s.start_date, end_date=s.end_date, is_current=s.is_current, created_at=s.created_at, org_id=s.org_id) for s in rows]


@router.post("/sessions", response_model=SessionResponse, status_code=201, dependencies=[_write])
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.is_current:
        await db.execute(update(AcademicSession).where(AcademicSession.org_id == current_user.org_id).values(is_current=False))
    s = AcademicSession(**payload.model_dump(), org_id=current_user.org_id)
    db.add(s)
    await db.flush()
    return SessionResponse(id=s.id, name=s.name, term=s.term, start_date=s.start_date, end_date=s.end_date, is_current=s.is_current, created_at=s.created_at, org_id=s.org_id)


@router.delete("/sessions/{session_id}", status_code=204, dependencies=[_write])
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(select(AcademicSession).where(AcademicSession.id == session_id, AcademicSession.org_id == current_user.org_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found.")
    await db.delete(s)


@router.get("/houses", response_model=list[HouseResponse], dependencies=[_read])
async def list_houses(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(SchoolHouse).where(SchoolHouse.org_id == current_user.org_id).order_by(SchoolHouse.name))).scalars().all()
    return [HouseResponse(id=h.id, name=h.name, color=h.color, motto=h.motto, created_at=h.created_at, org_id=h.org_id) for h in rows]


@router.post("/houses", response_model=HouseResponse, status_code=201, dependencies=[_write])
async def create_house(payload: HouseCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    h = SchoolHouse(**payload.model_dump(), org_id=current_user.org_id)
    db.add(h)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A house with that name already exists.")
    return HouseResponse(id=h.id, name=h.name, color=h.color, motto=h.motto, created_at=h.created_at, org_id=h.org_id)


@router.delete("/houses/{house_id}", status_code=204, dependencies=[_write])
async def delete_house(house_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    h = (await db.execute(select(SchoolHouse).where(SchoolHouse.id == house_id, SchoolHouse.org_id == current_user.org_id))).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="House not found.")
    await db.delete(h)


@router.get("/grading-bands", response_model=list[BandResponse], dependencies=[_read])
async def list_bands(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(GradingBand).where(GradingBand.org_id == current_user.org_id).order_by(GradingBand.min_score.desc()))).scalars().all()
    return [BandResponse(id=b.id, grade=b.grade, min_score=float(b.min_score), max_score=float(b.max_score), remark=b.remark, created_at=b.created_at, org_id=b.org_id) for b in rows]


@router.post("/grading-bands", response_model=BandResponse, status_code=201, dependencies=[_write])
async def create_band(payload: BandCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.max_score < payload.min_score:
        raise HTTPException(status_code=422, detail="max_score must be ≥ min_score.")
    b = GradingBand(grade=payload.grade, min_score=money(payload.min_score), max_score=money(payload.max_score), remark=payload.remark, org_id=current_user.org_id)
    db.add(b)
    await db.flush()
    return BandResponse(id=b.id, grade=b.grade, min_score=float(b.min_score), max_score=float(b.max_score), remark=b.remark, created_at=b.created_at, org_id=b.org_id)


@router.delete("/grading-bands/{band_id}", status_code=204, dependencies=[_write])
async def delete_band(band_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    b = (await db.execute(select(GradingBand).where(GradingBand.id == band_id, GradingBand.org_id == current_user.org_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Band not found.")
    await db.delete(b)


# ── Custom Fields ────────────────────────────────────────────────────────────────

@router.get("/custom-fields", response_model=list[FieldDefResponse], dependencies=[_read])
async def list_field_defs(entity_type: str | None = Query(default=None), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    base = select(CustomFieldDefinition).where(CustomFieldDefinition.org_id == current_user.org_id, CustomFieldDefinition.is_deleted == False)  # noqa: E712
    if entity_type:
        base = base.where(CustomFieldDefinition.entity_type == entity_type)
    rows = (await db.execute(base.order_by(CustomFieldDefinition.label))).scalars().all()
    return [FieldDefResponse(id=f.id, entity_type=f.entity_type, field_key=f.field_key, label=f.label, field_type=f.field_type, options=f.options, required=f.required, created_at=f.created_at, org_id=f.org_id) for f in rows]


@router.post("/custom-fields", response_model=FieldDefResponse, status_code=201, dependencies=[_write])
async def create_field_def(payload: FieldDefCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    f = CustomFieldDefinition(entity_type=payload.entity_type, field_key=payload.field_key, label=payload.label,
                              field_type=payload.field_type, options=payload.options, required=payload.required, org_id=current_user.org_id)
    db.add(f)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That field key already exists for this entity.")
    return FieldDefResponse(id=f.id, entity_type=f.entity_type, field_key=f.field_key, label=f.label, field_type=f.field_type, options=f.options, required=f.required, created_at=f.created_at, org_id=f.org_id)


@router.delete("/custom-fields/{field_id}", status_code=204, dependencies=[_write])
async def delete_field_def(field_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    f = (await db.execute(select(CustomFieldDefinition).where(CustomFieldDefinition.id == field_id, CustomFieldDefinition.org_id == current_user.org_id, CustomFieldDefinition.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not f:
        raise HTTPException(status_code=404, detail="Field not found.")
    f.is_deleted = True
    f.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.get("/custom-fields/values", response_model=list[FieldValueResponse], dependencies=[_read])
async def list_field_values(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(CustomFieldValue).where(CustomFieldValue.org_id == current_user.org_id, CustomFieldValue.entity_type == entity_type, CustomFieldValue.entity_id == entity_id))).scalars().all()
    return [FieldValueResponse(id=v.id, field_id=v.field_id, entity_type=v.entity_type, entity_id=v.entity_id, value=v.value, org_id=v.org_id) for v in rows]


@router.post("/custom-fields/values", response_model=FieldValueResponse, dependencies=[_write])
async def set_field_value(payload: FieldValueSet, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    fd = (await db.execute(select(CustomFieldDefinition).where(CustomFieldDefinition.id == payload.field_id, CustomFieldDefinition.org_id == current_user.org_id, CustomFieldDefinition.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not fd:
        raise HTTPException(status_code=404, detail="field not found.")
    v = (await db.execute(select(CustomFieldValue).where(CustomFieldValue.org_id == current_user.org_id, CustomFieldValue.field_id == payload.field_id, CustomFieldValue.entity_id == payload.entity_id))).scalar_one_or_none()
    if v:
        v.value = payload.value
    else:
        v = CustomFieldValue(field_id=payload.field_id, entity_type=payload.entity_type, entity_id=payload.entity_id, value=payload.value, org_id=current_user.org_id)
        db.add(v)
    await db.flush()
    return FieldValueResponse(id=v.id, field_id=v.field_id, entity_type=v.entity_type, entity_id=v.entity_id, value=v.value, org_id=v.org_id)


# ── Voting ──────────────────────────────────────────────────────────────────────

async def _poll_response(db, p: Poll, org_id: str, voter_id: str | None) -> PollResponse:
    opts = (await db.execute(select(PollOption).where(PollOption.poll_id == p.id).order_by(PollOption.created_at))).scalars().all()
    counts = dict((oid, c) for oid, c in (await db.execute(
        select(PollVote.option_id, func.count(PollVote.id)).where(PollVote.poll_id == p.id).group_by(PollVote.option_id)
    )).all())
    total = sum(counts.values())
    my = (await db.execute(select(PollVote.option_id).where(PollVote.poll_id == p.id, PollVote.voter_id == voter_id))).scalar_one_or_none() if voter_id else None
    return PollResponse(id=p.id, title=p.title, description=p.description, status=p.status, closes_at=p.closes_at,
                        total_votes=total, options=[PollOptionResult(id=o.id, label=o.label, votes=counts.get(o.id, 0)) for o in opts],
                        my_vote_option_id=my, created_at=p.created_at, org_id=p.org_id)


@router.get("/polls", response_model=PollListResponse, dependencies=[Depends(require_module("school"))])
async def list_polls(status: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
                     db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    base = select(Poll).where(Poll.org_id == current_user.org_id, Poll.is_deleted == False)  # noqa: E712
    if status:
        base = base.where(Poll.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(Poll.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = [await _poll_response(db, p, current_user.org_id, current_user.id) for p in rows]
    return PollListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/polls", response_model=PollResponse, status_code=201, dependencies=[_write])
async def create_poll(payload: PollCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = Poll(title=payload.title, description=payload.description, closes_at=payload.closes_at, status="open", created_by=current_user.id, org_id=current_user.org_id)
    db.add(p)
    await db.flush()
    for label in payload.options:
        db.add(PollOption(poll_id=p.id, label=label, org_id=current_user.org_id))
    await db.flush()
    return await _poll_response(db, p, current_user.org_id, current_user.id)


@router.post("/polls/{poll_id}/close", response_model=PollResponse, dependencies=[_write])
async def close_poll(poll_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(Poll).where(Poll.id == poll_id, Poll.org_id == current_user.org_id, Poll.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Poll not found.")
    p.status = "closed"
    await db.flush()
    return await _poll_response(db, p, current_user.org_id, current_user.id)


@router.delete("/polls/{poll_id}", status_code=204, dependencies=[_write])
async def delete_poll(poll_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(Poll).where(Poll.id == poll_id, Poll.org_id == current_user.org_id, Poll.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Poll not found.")
    p.is_deleted = True
    p.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.post("/polls/{poll_id}/vote", response_model=PollResponse, dependencies=[Depends(require_module("school"))])
async def cast_vote(poll_id: str, payload: CastVote, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Any authenticated member can vote once. Integrity: the unique
    (poll_id, voter_id) constraint makes a second vote a hard 409."""
    p = (await db.execute(select(Poll).where(Poll.id == poll_id, Poll.org_id == current_user.org_id, Poll.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Poll not found.")
    if p.status != "open":
        raise HTTPException(status_code=409, detail="This poll is closed.")
    opt = (await db.execute(select(PollOption).where(PollOption.id == payload.option_id, PollOption.poll_id == p.id))).scalar_one_or_none()
    if not opt:
        raise HTTPException(status_code=404, detail="option not found for this poll.")
    db.add(PollVote(poll_id=p.id, option_id=opt.id, voter_id=current_user.id, org_id=current_user.org_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You have already voted in this poll.")
    return await _poll_response(db, p, current_user.org_id, current_user.id)


# ── Mailbox (announcements) ───────────────────────────────────────────────────────

@router.post("/mailbox/messages", response_model=MessageResponse, status_code=201, dependencies=[_write])
async def send_message(payload: MessageCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    recipients = set(payload.recipient_ids)
    if payload.all_staff:
        staff_ids = (await db.execute(select(User.id).where(User.org_id == current_user.org_id, User.is_deleted == False, User.status == UserStatus.ACTIVE))).scalars().all()  # noqa: E712
        recipients.update(staff_ids)
    recipients.discard(current_user.id)
    if not recipients:
        raise HTTPException(status_code=422, detail="No recipients.")
    m = MailboxMessage(subject=payload.subject, body=payload.body, sender_id=current_user.id,
                       audience="all_staff" if payload.all_staff else "custom", org_id=current_user.org_id)
    db.add(m)
    await db.flush()
    for rid in recipients:
        db.add(MailboxRecipient(message_id=m.id, recipient_id=rid, org_id=current_user.org_id))
    await db.flush()
    return MessageResponse(id=m.id, subject=m.subject, body=m.body, sender_id=m.sender_id, audience=m.audience,
                           recipient_count=len(recipients), read_count=0, created_at=m.created_at, org_id=m.org_id)


@router.get("/mailbox/sent", response_model=list[MessageResponse], dependencies=[_read])
async def list_sent(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(MailboxMessage).where(MailboxMessage.org_id == current_user.org_id, MailboxMessage.sender_id == current_user.id, MailboxMessage.is_deleted == False).order_by(MailboxMessage.created_at.desc()))).scalars().all()  # noqa: E712
    out = []
    for m in rows:
        rc = (await db.execute(select(func.count()).select_from(MailboxRecipient).where(MailboxRecipient.message_id == m.id))).scalar() or 0
        read = (await db.execute(select(func.count()).select_from(MailboxRecipient).where(MailboxRecipient.message_id == m.id, MailboxRecipient.read_at.isnot(None)))).scalar() or 0
        out.append(MessageResponse(id=m.id, subject=m.subject, body=m.body, sender_id=m.sender_id, audience=m.audience, recipient_count=rc, read_count=read, created_at=m.created_at, org_id=m.org_id))
    return out


@router.get("/mailbox/inbox", response_model=list[InboxItemResponse])
async def my_inbox(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(MailboxRecipient, MailboxMessage)
        .join(MailboxMessage, MailboxMessage.id == MailboxRecipient.message_id)
        .where(MailboxRecipient.recipient_id == current_user.id, MailboxRecipient.org_id == current_user.org_id, MailboxMessage.is_deleted == False)  # noqa: E712
        .order_by(MailboxMessage.created_at.desc())
    )).all()
    return [InboxItemResponse(recipient_row_id=r.id, message_id=m.id, subject=m.subject, body=m.body, sender_id=m.sender_id, read_at=r.read_at, created_at=m.created_at) for r, m in rows]


@router.post("/mailbox/inbox/{recipient_row_id}/read", status_code=204)
async def mark_read(recipient_row_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(MailboxRecipient).where(MailboxRecipient.id == recipient_row_id, MailboxRecipient.recipient_id == current_user.id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Inbox item not found.")
    if r.read_at is None:
        r.read_at = datetime.now(timezone.utc)
        await db.flush()


# ── Mobile Manager ───────────────────────────────────────────────────────────────

def _mobile_response(d: MobileDevice) -> MobileDeviceResponse:
    return MobileDeviceResponse(id=d.id, user_id=d.user_id, push_token=d.push_token, platform=d.platform, label=d.label, is_active=d.is_active, last_seen_at=d.last_seen_at, created_at=d.created_at, org_id=d.org_id)


@router.post("/mobile/register", response_model=MobileDeviceResponse, status_code=201)
async def register_mobile(payload: MobileDeviceRegister, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Any authenticated user registers their own device's push token (idempotent on token)."""
    existing = (await db.execute(select(MobileDevice).where(MobileDevice.org_id == current_user.org_id, MobileDevice.push_token == payload.push_token))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.user_id = current_user.id
        existing.platform = payload.platform or existing.platform
        existing.label = payload.label or existing.label
        existing.is_active = True
        existing.last_seen_at = now
        await db.flush()
        return _mobile_response(existing)
    d = MobileDevice(user_id=current_user.id, push_token=payload.push_token, platform=payload.platform, label=payload.label, is_active=True, last_seen_at=now, org_id=current_user.org_id)
    db.add(d)
    await db.flush()
    return _mobile_response(d)


@router.get("/mobile/devices", response_model=list[MobileDeviceResponse], dependencies=[_read])
async def list_mobile_devices(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(MobileDevice).where(MobileDevice.org_id == current_user.org_id).order_by(MobileDevice.created_at.desc()))).scalars().all()
    return [_mobile_response(d) for d in rows]


@router.delete("/mobile/devices/{device_id}", status_code=204, dependencies=[_write])
async def delete_mobile_device(device_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = (await db.execute(select(MobileDevice).where(MobileDevice.id == device_id, MobileDevice.org_id == current_user.org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found.")
    await db.delete(d)


@router.get("/mobile/config", response_model=list[AppConfigResponse])
async def get_app_config(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Authenticated read — the mobile app fetches its config toggles."""
    rows = (await db.execute(select(MobileAppConfig).where(MobileAppConfig.org_id == current_user.org_id).order_by(MobileAppConfig.key))).scalars().all()
    return [AppConfigResponse(id=c.id, key=c.key, value=c.value, description=c.description, org_id=c.org_id) for c in rows]


@router.post("/mobile/config", response_model=AppConfigResponse, dependencies=[_write])
async def set_app_config(payload: AppConfigSet, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(MobileAppConfig).where(MobileAppConfig.org_id == current_user.org_id, MobileAppConfig.key == payload.key))).scalar_one_or_none()
    if c:
        c.value = payload.value
        c.description = payload.description if payload.description is not None else c.description
    else:
        c = MobileAppConfig(key=payload.key, value=payload.value, description=payload.description, org_id=current_user.org_id)
        db.add(c)
    await db.flush()
    return AppConfigResponse(id=c.id, key=c.key, value=c.value, description=c.description, org_id=c.org_id)
