"""
Bulk SMS Router (Phase 6.6)
===========================

Admin-only blast messaging to students, parents, teachers, or a specific
class. Recipient resolution is always server-side — the frontend sends
(target_type, target_value) and the backend looks up the matching users
from its own data.

Restrictions:
  - `school:write` permission required
  - Additional gate: only `org_admin` / `manager` / `super_admin` slugs can
    actually send. Teachers don't blast parents.

Provider:
  - Pluggable (see `app.services.sms`). Default is `mock` which returns
    deterministic delivery results so the demo is stable.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.services.audit_service import log_action
from app.models.audit import AuditAction
from app.core.ratelimit import rate_limit_auth
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.organization import Organization
from app.models.role import Role
from app.models.modules.school import (
    Student, SchoolClass, ParentGuardian,
)
from app.models.sms import (
    SmsCampaign, SmsMessage, SmsTargetType,
    SmsCampaignStatus, SmsMessageStatus,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.services.sms import (
    get_provider, estimate_sms_units, default_sender_id,
    estimate_sms_cost_ngn, COST_PER_UNIT_NGN,
    check_rate_limit, normalise_phone_e164,
)

router = APIRouter(
    prefix="/sms",
    tags=["Bulk SMS"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school_admin:read"))
_can_write = Depends(PermissionChecker("school_admin:write"))


ADMIN_SLUGS = {"org_admin", "manager", "super_admin"}


def _require_admin(user: User) -> None:
    """Extra gate beyond `school:write` — teachers have write but shouldn't
    send bulk SMS. Raises 403 on non-admins."""
    if user.is_superadmin:
        return
    if any(r.slug in ADMIN_SLUGS for r in user.roles):
        return
    raise HTTPException(403, detail="Only administrators can send bulk SMS")


# ── Recipient resolution ─────────────────────────────────────────────────────


async def _resolve_recipients(
    db: AsyncSession,
    *,
    org_id: str,
    target_type: SmsTargetType,
    target_value: Any,
) -> tuple[list[User], str]:
    """Return (users, human_label). Only users with a non-empty phone are
    returned — callers use the label in campaign display."""
    users: list[User] = []
    label = ""

    if target_type == SmsTargetType.ALL_STUDENTS:
        rows = (await db.execute(
            select(User).join(User.roles).where(
                User.org_id == org_id,
                User.phone.isnot(None),
                User.phone != "",
                Role.slug == "student",
            ).distinct()
        )).scalars().all()
        users = list(rows)
        label = "All students"

    elif target_type == SmsTargetType.ALL_PARENTS:
        rows = (await db.execute(
            select(User).join(User.roles).where(
                User.org_id == org_id,
                User.phone.isnot(None),
                User.phone != "",
                Role.slug == "parent",
            ).distinct()
        )).scalars().all()
        users = list(rows)
        label = "All parents"

    elif target_type == SmsTargetType.ALL_TEACHERS:
        rows = (await db.execute(
            select(User).join(User.roles).where(
                User.org_id == org_id,
                User.phone.isnot(None),
                User.phone != "",
                Role.slug == "teacher",
            ).distinct()
        )).scalars().all()
        users = list(rows)
        label = "All teachers"

    elif target_type == SmsTargetType.CLASS:
        class_id = str(target_value or "")
        if not class_id:
            raise HTTPException(422, detail="target_value (class id) required")
        cls = (await db.execute(
            select(SchoolClass).where(
                SchoolClass.id == class_id,
                SchoolClass.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not cls:
            raise HTTPException(404, detail="Class not found")
        # Students of this class → their linked User rows with phones
        rows = (await db.execute(
            select(User).join(Student, Student.user_id == User.id).where(
                Student.org_id == org_id,
                Student.class_id == class_id,
                Student.is_deleted == False,
                User.phone.isnot(None),
                User.phone != "",
            )
        )).scalars().all()
        users = list(rows)
        label = f"Students in {cls.name}"

    elif target_type == SmsTargetType.CLASS_PARENTS:
        class_id = str(target_value or "")
        if not class_id:
            raise HTTPException(422, detail="target_value (class id) required")
        cls = (await db.execute(
            select(SchoolClass).where(
                SchoolClass.id == class_id,
                SchoolClass.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not cls:
            raise HTTPException(404, detail="Class not found")
        # Join: ParentGuardian.user_id → User where the student is in this class.
        rows = (await db.execute(
            select(User)
            .join(ParentGuardian, ParentGuardian.user_id == User.id)
            .join(Student, Student.id == ParentGuardian.student_id)
            .where(
                Student.class_id == class_id,
                Student.org_id == org_id,
                Student.is_deleted == False,
                User.phone.isnot(None),
                User.phone != "",
            ).distinct()
        )).scalars().all()
        users = list(rows)
        label = f"Parents of {cls.name}"

    elif target_type == SmsTargetType.CUSTOM:
        ids = target_value if isinstance(target_value, list) else []
        if not ids:
            raise HTTPException(422, detail="target_value (user id list) required")
        rows = (await db.execute(
            select(User).where(
                User.org_id == org_id,
                User.id.in_([str(i) for i in ids]),
                User.phone.isnot(None),
                User.phone != "",
            )
        )).scalars().all()
        users = list(rows)
        label = f"{len(users)} selected recipients"

    else:
        raise HTTPException(422, detail=f"Unsupported target type: {target_type}")

    # Deduplicate (a parent might match two targets in overlapping builds).
    seen: set[str] = set()
    unique: list[User] = []
    for u in users:
        if u.id in seen:
            continue
        seen.add(u.id)
        unique.append(u)
    return unique, label


def _coerce_target(target_type_str: str) -> SmsTargetType:
    try:
        return SmsTargetType(target_type_str)
    except ValueError:
        raise HTTPException(
            422,
            detail=f"Invalid target_type. Expected one of: {', '.join(t.value for t in SmsTargetType)}",
        )


# ── Dicts ────────────────────────────────────────────────────────────────────


def _campaign_dict(c: SmsCampaign, creator: User | None = None) -> dict[str, Any]:
    units = estimate_sms_units(c.body)
    return {
        "id": c.id,
        "subject": c.subject,
        "body": c.body,
        "sender_id": c.sender_id,
        "provider": c.provider,
        "target_type": c.target_type.value if hasattr(c.target_type, "value") else c.target_type,
        "target_value": c.target_value,
        "target_label": c.target_label,
        "total_recipients": c.total_recipients,
        "sent_count": c.sent_count,
        "delivered_count": c.delivered_count,
        "failed_count": c.failed_count,
        "status": c.status.value if hasattr(c.status, "value") else c.status,
        "created_by": c.created_by,
        "created_by_name": creator.full_name if creator else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "completed_at": c.completed_at.isoformat() if c.completed_at else None,
        "sms_units": units,
        # NGN cost for the *whole* campaign — surfaces in the logs row so
        # admins can budget at a glance. Unit cost is exposed too in case
        # the UI wants to render "₦4 per SMS unit" footnotes.
        "cost_ngn": round(units * COST_PER_UNIT_NGN * c.total_recipients, 2),
        "unit_cost_ngn": COST_PER_UNIT_NGN,
    }


def _message_dict(m: SmsMessage) -> dict[str, Any]:
    return {
        "id": m.id,
        "recipient_user_id": m.recipient_user_id,
        "recipient_name": m.recipient_name,
        "recipient_phone": m.recipient_phone,
        "status": m.status.value if hasattr(m.status, "value") else m.status,
        "error_message": m.error_message,
        "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
    }


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/recipients/preview", dependencies=[_can_read])
async def preview_recipients(
    target_type: str,
    target_value: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Compose screen calls this whenever target changes. Returns the count
    and a sample of names so the admin can sanity-check before sending."""
    _require_admin(current_user)
    t = _coerce_target(target_type)
    users, label = await _resolve_recipients(
        db, org_id=current_user.org_id, target_type=t, target_value=target_value,
    )
    # Sample for display — enough to reassure, not a full list.
    sample = [{"id": u.id, "name": u.full_name, "phone": u.phone} for u in users[:8]]
    return {
        "target_type": t.value,
        "target_label": label,
        "total": len(users),
        "sample": sample,
        # Cost preview is target-only here — body-aware cost is computed by
        # the frontend (it knows the message it's about to send).
        "unit_cost_ngn": COST_PER_UNIT_NGN,
    }


@router.post("/campaigns", status_code=201, dependencies=[_can_write, Depends(rate_limit_auth("sms_send"))])
async def send_campaign(
    payload: dict,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_admin(current_user)

    # Rate limit per org. The mock provider is fast enough that a careless
    # admin could fire 50 campaigns/min — real providers throttle hard at
    # similar shapes, so we surface the same 429 shape here.
    allowed, retry_in = check_rate_limit(current_user.org_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "reason": "Too many campaigns in a short window. Please slow down.",
                "retry_after_seconds": retry_in,
            },
            headers={"Retry-After": str(retry_in)},
        )

    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(422, detail="Message body is required")
    if len(body) > 1600:
        raise HTTPException(422, detail="Message body is too long (max 1600 chars)")

    t = _coerce_target(str(payload.get("target_type") or ""))
    target_value = payload.get("target_value")

    # Org lookup for default sender id
    org = (await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )).scalar_one_or_none()
    sender_id = str(payload.get("sender_id") or default_sender_id(org.name if org else None))
    if len(sender_id) > 11:
        raise HTTPException(422, detail="sender_id must be 11 chars or fewer")

    # Resolve recipients up front so we can short-circuit empty sends.
    recipients, label = await _resolve_recipients(
        db, org_id=current_user.org_id, target_type=t, target_value=target_value,
    )
    if not recipients:
        raise HTTPException(
            409,
            detail="No recipients matched — nobody with a phone number fits this target.",
        )

    provider = get_provider(payload.get("provider") or None)

    campaign = SmsCampaign(
        subject=(payload.get("subject") or None),
        body=body,
        sender_id=sender_id,
        provider=provider.name,
        created_by=current_user.id,
        target_type=t,
        target_value=target_value,
        target_label=label,
        total_recipients=len(recipients),
        status=SmsCampaignStatus.SENDING,
        org_id=current_user.org_id,
    )
    db.add(campaign)
    await db.flush()

    # Fan-out. Mock provider resolves synchronously and fast enough that
    # we don't need a background worker for the demo. For real providers
    # we'll return the campaign immediately and process in a queue.
    sent = 0
    delivered = 0
    failed = 0
    now = datetime.now(timezone.utc)

    for u in recipients:
        # Normalise to E.164 right before handing off — defensive even though
        # we also normalise at user-write time. A bad number short-circuits
        # to FAILED rather than tripping the provider with garbage input.
        e164 = normalise_phone_e164(u.phone)
        if not e164:
            failed += 1
            db.add(SmsMessage(
                campaign_id=campaign.id,
                recipient_user_id=u.id,
                recipient_name=u.full_name,
                recipient_phone=u.phone or "",
                status=SmsMessageStatus.FAILED,
                error_message="Invalid phone number",
                org_id=current_user.org_id,
            ))
            continue

        result = await provider.send(to=e164, body=body, sender_id=sender_id)
        if result.accepted:
            status = SmsMessageStatus.DELIVERED if result.delivered else (
                SmsMessageStatus.FAILED if result.error_message else SmsMessageStatus.SENT
            )
            sent += 1
            if result.delivered:
                delivered += 1
            elif result.error_message:
                failed += 1
        else:
            status = SmsMessageStatus.FAILED
            failed += 1

        db.add(SmsMessage(
            campaign_id=campaign.id,
            recipient_user_id=u.id,
            recipient_name=u.full_name,
            recipient_phone=e164,
            status=status,
            provider_message_id=result.provider_message_id,
            error_message=result.error_message,
            sent_at=now if result.accepted else None,
            delivered_at=now if result.delivered else None,
            org_id=current_user.org_id,
        ))

    campaign.sent_count = sent
    campaign.delivered_count = delivered
    campaign.failed_count = failed
    campaign.status = (
        SmsCampaignStatus.COMPLETED if sent > 0
        else SmsCampaignStatus.FAILED
    )
    campaign.completed_at = now
    await db.flush()

    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="SmsCampaign", resource_id=campaign.id,
        resource_label=f"SMS campaign to {campaign.total_recipients} recipient(s)",
        severity="warning",
        metadata={"recipients": campaign.total_recipients, "sent": sent, "failed": failed,
                  "target": label, "sender_id": sender_id},
        request=request,
    )
    return _campaign_dict(campaign, creator=current_user)


@router.get("/campaigns", dependencies=[_can_read])
async def list_campaigns(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_admin(current_user)
    query = select(SmsCampaign).where(SmsCampaign.org_id == current_user.org_id)
    if status:
        try:
            query = query.where(SmsCampaign.status == SmsCampaignStatus(status))
        except ValueError:
            raise HTTPException(422, detail=f"Invalid status: {status}")

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(SmsCampaign.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    # Hydrate creator names in one batch.
    creator_ids = {r.created_by for r in rows if r.created_by}
    creators: dict[str, User] = {}
    if creator_ids:
        for u in (await db.execute(
            select(User).where(User.id.in_(creator_ids))
        )).scalars().all():
            creators[u.id] = u

    return {
        "items": [_campaign_dict(c, creator=creators.get(c.created_by)) for c in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/campaigns/{campaign_id}", dependencies=[_can_read])
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_admin(current_user)
    c = (await db.execute(
        select(SmsCampaign).where(
            SmsCampaign.id == campaign_id,
            SmsCampaign.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(404, detail="Campaign not found")

    creator = None
    if c.created_by:
        creator = (await db.execute(select(User).where(User.id == c.created_by))).scalar_one_or_none()

    msgs = (await db.execute(
        select(SmsMessage).where(
            SmsMessage.campaign_id == campaign_id,
            SmsMessage.org_id == current_user.org_id,
        ).order_by(SmsMessage.recipient_name.asc())
    )).scalars().all()

    return {
        "campaign": _campaign_dict(c, creator=creator),
        "messages": [_message_dict(m) for m in msgs],
    }


@router.post("/campaigns/{campaign_id}/resend", status_code=201, dependencies=[_can_write])
async def resend_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Re-issue a campaign with the same body + target. Recipients are
    re-resolved at send time so anyone added/removed since the original
    send is included/excluded automatically."""
    _require_admin(current_user)

    original = (await db.execute(
        select(SmsCampaign).where(
            SmsCampaign.id == campaign_id,
            SmsCampaign.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not original:
        raise HTTPException(404, detail="Campaign not found")

    # Reuse the same `send_campaign` logic by delegating with a synthesised
    # payload. We deliberately don't share recipients — re-resolving against
    # the live data is the correct behaviour for a "resend".
    payload = {
        "subject": (original.subject + " (resend)") if original.subject else "Resend",
        "body": original.body,
        "sender_id": original.sender_id,
        "target_type": original.target_type.value if hasattr(original.target_type, "value") else original.target_type,
        "target_value": original.target_value,
        "provider": original.provider,
    }
    return await send_campaign(payload, db=db, current_user=current_user)


@router.post("/webhook/{provider_name}", include_in_schema=False)
async def provider_webhook(
    provider_name: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Async DLR (Delivery Report) webhook stub.

    Real providers (Termii, Africa's Talking, Twilio) POST here when they've
    confirmed delivery to the handset. Right now this only handles the
    common shape: `{provider_message_id, status, ...}`. We update the
    matching SmsMessage and bump the campaign counters.

    Not in OpenAPI (`include_in_schema=False`) — wired but not part of the
    public surface yet. Auth happens via shared-secret header in production
    (TODO when we plug in a real provider)."""
    pid = str(payload.get("provider_message_id") or payload.get("message_id") or "")
    raw_status = str(payload.get("status") or "").lower()
    if not pid:
        raise HTTPException(422, detail="provider_message_id required")

    msg = (await db.execute(
        select(SmsMessage).where(SmsMessage.provider_message_id == pid)
    )).scalar_one_or_none()
    if not msg:
        # Provider may DLR before our DB commits — return 202 so they retry.
        raise HTTPException(202, detail="Message not yet visible")

    msg.provider_status_raw = payload
    if raw_status in ("delivered", "delivrd", "success"):
        if msg.status != SmsMessageStatus.DELIVERED:
            msg.status = SmsMessageStatus.DELIVERED
            msg.delivered_at = datetime.now(timezone.utc)
            # Bump the campaign counter atomically.
            await db.execute(
                SmsCampaign.__table__.update()
                .where(SmsCampaign.id == msg.campaign_id)
                .values(delivered_count=SmsCampaign.delivered_count + 1)
            )
    elif raw_status in ("failed", "rejected", "expired", "undelivered"):
        if msg.status != SmsMessageStatus.FAILED:
            msg.status = SmsMessageStatus.FAILED
            msg.error_message = str(payload.get("reason") or "Provider reported failure")
            await db.execute(
                SmsCampaign.__table__.update()
                .where(SmsCampaign.id == msg.campaign_id)
                .values(failed_count=SmsCampaign.failed_count + 1)
            )
    await db.flush()
    return {"ok": True}


@router.get("/classes", dependencies=[_can_read])
async def list_classes_for_sms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Minimal class picker for the compose screen. Just id + name + count
    of linked students. Avoids needing a full /school/classes endpoint."""
    _require_admin(current_user)
    rows = (await db.execute(
        select(SchoolClass).where(SchoolClass.org_id == current_user.org_id)
    )).scalars().all()
    # Attach student counts in a single query.
    count_rows = (await db.execute(
        select(Student.class_id, func.count(Student.id)).where(
            Student.org_id == current_user.org_id,
            Student.is_deleted == False,
            Student.class_id.isnot(None),
        ).group_by(Student.class_id)
    )).all()
    counts = {cid: int(n) for (cid, n) in count_rows}
    return {
        "items": [
            {"id": c.id, "name": c.name, "level": c.level, "student_count": counts.get(c.id, 0)}
            for c in rows
        ],
    }
