"""Staff Confirmation router (HR), prefix ``/hr``.

The probation → confirmed workflow. Confidential HR admin — gated ``hr:write``.
Confirming a case flips the staff member's HRProfile.employment_status to
``active``; the case row is the audit trail.

ENDPOINTS:
  GET    /hr/confirmations            (?status)
  POST   /hr/confirmations            — start a confirmation (pending)
  PATCH  /hr/confirmations/{id}/decide — confirm / decline (idempotent 409)
  DELETE /hr/confirmations/{id}       — cancel a still-pending case
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.hrm import HRProfile
from app.models.hr_confirmation import StaffConfirmation
from app.schemas.hr_confirmation import ConfirmationCreate, ConfirmationDecide, ConfirmationResponse

router = APIRouter(prefix="/hr", tags=["HR — Confirmation"])

_can_hr = Depends(PermissionChecker("hr:write"))

CONFIRMED_STATUS = "active"   # employment_status value a confirmed staff member holds


async def _profile(db: AsyncSession, org_id: str, user_id: str, create: bool = False) -> HRProfile | None:
    p = (await db.execute(select(HRProfile).where(
        HRProfile.user_id == user_id, HRProfile.org_id == org_id, HRProfile.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if p is None and create:
        p = HRProfile(user_id=user_id, org_id=org_id)
        db.add(p)
    return p


def _response(c: StaffConfirmation, staff_name: str | None, employment_status: str | None) -> ConfirmationResponse:
    return ConfirmationResponse(
        id=c.id, staff_user_id=c.staff_user_id, staff_name=staff_name, employment_status=employment_status,
        probation_start=c.probation_start, due_date=c.due_date, status=c.status,
        recommendation=c.recommendation, decided_at=c.decided_at, notes=c.notes,
        created_at=c.created_at, org_id=c.org_id,
    )


@router.get("/confirmations", response_model=list[ConfirmationResponse], dependencies=[_can_hr])
async def list_confirmations(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(StaffConfirmation).where(StaffConfirmation.org_id == current_user.org_id, StaffConfirmation.is_deleted == False)  # noqa: E712
    if status:
        q = q.where(StaffConfirmation.status == status)
    rows = (await db.execute(q.order_by(StaffConfirmation.created_at.desc()))).scalars().all()
    ids = {c.staff_user_id for c in rows}
    users = {u.id: u for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()} if ids else {}
    profiles = {p.user_id: p for p in (await db.execute(
        select(HRProfile).where(HRProfile.org_id == current_user.org_id, HRProfile.user_id.in_(ids))
    )).scalars().all()} if ids else {}
    return [_response(c, users.get(c.staff_user_id).full_name if users.get(c.staff_user_id) else None,
                      profiles.get(c.staff_user_id).employment_status if profiles.get(c.staff_user_id) else None) for c in rows]


@router.post("/confirmations", response_model=ConfirmationResponse, status_code=201, dependencies=[_can_hr])
async def start_confirmation(payload: ConfirmationCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    staff = (await db.execute(select(User).where(
        User.id == payload.staff_user_id, User.org_id == current_user.org_id, User.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    c = StaffConfirmation(
        staff_user_id=staff.id, org_id=current_user.org_id,
        probation_start=payload.probation_start, due_date=payload.due_date,
        recommendation=(payload.recommendation or None), status="pending",
    )
    db.add(c)
    await db.flush()
    prof = await _profile(db, current_user.org_id, staff.id)
    return _response(c, staff.full_name, prof.employment_status if prof else None)


@router.patch("/confirmations/{conf_id}/decide", response_model=ConfirmationResponse, dependencies=[_can_hr])
async def decide_confirmation(conf_id: str, payload: ConfirmationDecide, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(StaffConfirmation).where(
        StaffConfirmation.id == conf_id, StaffConfirmation.org_id == current_user.org_id, StaffConfirmation.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Confirmation not found.")
    if c.status != "pending":
        raise HTTPException(status_code=409, detail=f"This confirmation is already {c.status}.")

    staff = (await db.execute(select(User).where(User.id == c.staff_user_id))).scalar_one_or_none()
    c.decided_by = current_user.id
    c.decided_at = datetime.now(timezone.utc)
    if payload.notes:
        c.notes = payload.notes

    employment_status = None
    if payload.decision == "confirm":
        c.status = "confirmed"
        prof = await _profile(db, current_user.org_id, c.staff_user_id, create=True)
        prof.employment_status = CONFIRMED_STATUS     # probation → active (confirmed)
        employment_status = prof.employment_status
    else:
        c.status = "declined"
        prof = await _profile(db, current_user.org_id, c.staff_user_id)
        employment_status = prof.employment_status if prof else None
    await db.flush()
    return _response(c, staff.full_name if staff else None, employment_status)


@router.delete("/confirmations/{conf_id}", status_code=204, dependencies=[_can_hr])
async def cancel_confirmation(conf_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(StaffConfirmation).where(
        StaffConfirmation.id == conf_id, StaffConfirmation.org_id == current_user.org_id, StaffConfirmation.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Confirmation not found.")
    if c.status != "pending":
        raise HTTPException(status_code=409, detail="Only a pending confirmation can be cancelled.")
    c.is_deleted = True
    c.deleted_at = datetime.now(timezone.utc)
    await db.flush()
