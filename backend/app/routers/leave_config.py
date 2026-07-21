"""Leave configuration + entitlements + assignment (HR Leave completion).

Layers three surfaces on top of the existing Leave module, keeping its LeaveType
enum unchanged:
  • Configure   — per-type policy (default days / approval / active). hr:write.
  • Entitlements — a staff member's balances (allocated − used = remaining). Self,
                   or any staff for hr:write via ?user_id.
  • Assign Leave — admin books an APPROVED leave on a staff member's behalf,
                   reusing LeaveApplication. hr:write.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.leave import LeaveApplication, LeaveType, LeaveStatus
from app.models.leave_config import LeavePolicy, DEFAULT_LEAVE_DAYS
from app.schemas.leave_config import (
    LeavePolicyUpdate, LeavePolicyResponse, EntitlementRow, AssignLeaveCreate,
)
from app.schemas.leave import LeaveApplicationResponse

router = APIRouter(prefix="/leave", tags=["Leave — Config & Entitlements"])

_can_hr = Depends(PermissionChecker("hr:write"))


def _label(lt: LeaveType) -> str:
    return lt.value.replace("_", " ").title()


async def _policies_map(db: AsyncSession, org_id: str) -> dict[LeaveType, LeavePolicy]:
    rows = (await db.execute(select(LeavePolicy).where(LeavePolicy.org_id == org_id))).scalars().all()
    return {p.leave_type: p for p in rows}


def _effective(lt: LeaveType, p: LeavePolicy | None) -> tuple[int, bool, bool]:
    """(allocated default_days, requires_approval, is_active) — stored row or defaults."""
    if p:
        return p.default_days, p.requires_approval, p.is_active
    return DEFAULT_LEAVE_DAYS.get(lt.value, 0), True, True


# ── Configure (policies) ──────────────────────────────────────────────────────

@router.get("/policies", response_model=list[LeavePolicyResponse], dependencies=[_can_hr])
async def list_policies(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    stored = await _policies_map(db, current_user.org_id)
    out = []
    for lt in LeaveType:
        days, appr, active = _effective(lt, stored.get(lt))
        out.append(LeavePolicyResponse(leave_type=lt.value, label=_label(lt), default_days=days, requires_approval=appr, is_active=active))
    return out


@router.put("/policies/{leave_type}", response_model=LeavePolicyResponse, dependencies=[_can_hr])
async def upsert_policy(leave_type: LeaveType, payload: LeavePolicyUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(LeavePolicy).where(
        LeavePolicy.org_id == current_user.org_id, LeavePolicy.leave_type == leave_type
    ))).scalar_one_or_none()
    if p:
        p.default_days = payload.default_days
        p.requires_approval = payload.requires_approval
        p.is_active = payload.is_active
    else:
        p = LeavePolicy(org_id=current_user.org_id, leave_type=leave_type,
                        default_days=payload.default_days, requires_approval=payload.requires_approval, is_active=payload.is_active)
        db.add(p)
    await db.flush()
    return LeavePolicyResponse(leave_type=leave_type.value, label=_label(leave_type),
                               default_days=p.default_days, requires_approval=p.requires_approval, is_active=p.is_active)


# ── Entitlements ──────────────────────────────────────────────────────────────

@router.get("/entitlements", response_model=list[EntitlementRow])
async def entitlements(
    user_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Self by default; viewing someone else requires hr:write.
    target_id = user_id or current_user.id
    if target_id != current_user.id:
        if not current_user.has_permission("hr:write"):
            raise HTTPException(status_code=403, detail="Not allowed to view another staff member’s entitlements.")
        target = (await db.execute(select(User).where(User.id == target_id, User.org_id == current_user.org_id, User.is_deleted == False))).scalar_one_or_none()  # noqa: E712
        if not target:
            raise HTTPException(status_code=404, detail="Staff member not found.")

    stored = await _policies_map(db, current_user.org_id)
    year = datetime.now(timezone.utc).year

    # Approved leave for this user in the current year → used days per type.
    approved = (await db.execute(select(LeaveApplication).where(
        LeaveApplication.org_id == current_user.org_id,
        LeaveApplication.user_id == target_id,
        LeaveApplication.status == LeaveStatus.APPROVED,
        LeaveApplication.is_deleted == False,  # noqa: E712
    ))).scalars().all()
    used: dict[str, int] = {}
    for a in approved:
        if a.start_date and a.start_date.year == year:
            used[a.leave_type.value] = used.get(a.leave_type.value, 0) + ((a.end_date - a.start_date).days + 1)

    out = []
    for lt in LeaveType:
        allocated, _appr, active = _effective(lt, stored.get(lt))
        if not active:
            continue
        u = used.get(lt.value, 0)
        out.append(EntitlementRow(leave_type=lt.value, label=_label(lt), allocated=allocated, used=u, remaining=allocated - u))
    return out


# ── Assign Leave (admin, on behalf) ───────────────────────────────────────────

@router.post("/assign", response_model=LeaveApplicationResponse, status_code=201, dependencies=[_can_hr])
async def assign_leave(payload: AssignLeaveCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="end_date: must be on or after start_date")
    staff = (await db.execute(select(User).where(
        User.id == payload.user_id, User.org_id == current_user.org_id, User.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    app = LeaveApplication(
        org_id=current_user.org_id, user_id=staff.id, leave_type=payload.leave_type,
        start_date=payload.start_date, end_date=payload.end_date, reason=payload.reason,
        status=LeaveStatus.APPROVED, approver_id=current_user.id, decided_at=datetime.now(timezone.utc),
        decision_note="Assigned by HR.",
    )
    db.add(app)
    await db.flush()
    return LeaveApplicationResponse(
        id=app.id, user_id=app.user_id, org_id=app.org_id,
        applicant_name=staff.full_name, applicant_email=staff.email,
        leave_type=app.leave_type, start_date=app.start_date, end_date=app.end_date,
        days=(app.end_date - app.start_date).days + 1, reason=app.reason, status=app.status,
        approver_id=app.approver_id, approver_name=current_user.full_name,
        decided_at=app.decided_at, decision_note=app.decision_note, created_at=app.created_at,
    )
