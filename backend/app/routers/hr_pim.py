"""PIM extras router (HR), prefix ``/hr``.

Staff Account Numbers (payroll bank details, reusing HRProfile) and the Staff
Transfer Log (dept moves that also update the staff record). Confidential HR
admin — gated ``hr:write``. Transfer endpoints are added in the transfer batch.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.role import Role, user_roles
from app.models.hrm import HRProfile
from app.models.hr_transfer import StaffTransfer
from app.schemas.hr_pim import AccountRow, AccountUpdate, TransferCreate, TransferResponse

router = APIRouter(prefix="/hr", tags=["HR — PIM"])

_can_hr = Depends(PermissionChecker("hr:write"))


def _non_employee_ids():
    """Sub-select of user ids holding a student/parent role — excluded from the
    employee (payroll) population."""
    return (
        select(user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(Role.slug.in_(("student", "parent")))
    )


def _account_row(u: User, p: HRProfile | None) -> AccountRow:
    return AccountRow(
        user_id=u.id, full_name=u.full_name, email=u.email,
        staff_id=(p.staff_id if p else None), job_title=u.job_title, department=u.department,
        bank_name=(p.bank_name if p else None),
        bank_account_name=(p.bank_account_name if p else None),
        bank_account_number=(p.bank_account_number if p else None),
    )


# ── Staff Account Numbers ─────────────────────────────────────────────────────

@router.get("/pim/accounts", response_model=list[AccountRow], dependencies=[_can_hr])
async def list_accounts(
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(User).where(
        User.org_id == current_user.org_id,
        User.is_deleted == False,  # noqa: E712
        User.id.notin_(_non_employee_ids()),
    )
    if search:
        like = f"%{search}%"
        q = q.where(or_(User.full_name.ilike(like), User.email.ilike(like)))
    users = (await db.execute(q.order_by(User.full_name))).scalars().all()

    profiles = {
        p.user_id: p for p in (await db.execute(
            select(HRProfile).where(HRProfile.org_id == current_user.org_id, HRProfile.is_deleted == False)  # noqa: E712
        )).scalars().all()
    }
    return [_account_row(u, profiles.get(u.id)) for u in users]


@router.patch("/pim/accounts/{user_id}", response_model=AccountRow, dependencies=[_can_hr])
async def update_account(
    user_id: str,
    payload: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    user = (await db.execute(select(User).where(
        User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Staff member not found.")

    profile = (await db.execute(select(HRProfile).where(
        HRProfile.user_id == user_id, HRProfile.org_id == current_user.org_id, HRProfile.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not profile:
        profile = HRProfile(user_id=user_id, org_id=current_user.org_id)
        db.add(profile)
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(profile, f, v)
    await db.flush()
    return _account_row(user, profile)


# ── Staff Transfer Log ────────────────────────────────────────────────────────

def _transfer_response(t: StaffTransfer, staff_name: str | None = None) -> TransferResponse:
    return TransferResponse(
        id=t.id, staff_user_id=t.staff_user_id, staff_name=staff_name,
        from_department=t.from_department, to_department=t.to_department, to_unit=t.to_unit,
        effective_date=t.effective_date, reason=t.reason, created_at=t.created_at, org_id=t.org_id,
    )


@router.get("/pim/transfers", response_model=list[TransferResponse], dependencies=[_can_hr])
async def list_transfers(
    staff_user_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(StaffTransfer).where(StaffTransfer.org_id == current_user.org_id, StaffTransfer.is_deleted == False)  # noqa: E712
    if staff_user_id:
        q = q.where(StaffTransfer.staff_user_id == staff_user_id)
    rows = (await db.execute(q.order_by(StaffTransfer.created_at.desc()))).scalars().all()
    ids = {t.staff_user_id for t in rows}
    names = dict((uid, name) for uid, name in (await db.execute(
        select(User.id, User.full_name).where(User.id.in_(ids))
    )).all()) if ids else {}
    return [_transfer_response(t, names.get(t.staff_user_id)) for t in rows]


@router.post("/pim/transfers", response_model=TransferResponse, status_code=201, dependencies=[_can_hr])
async def create_transfer(
    payload: TransferCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    staff = (await db.execute(select(User).where(
        User.id == payload.staff_user_id, User.org_id == current_user.org_id, User.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found.")

    from_dept = staff.department                      # snapshot before the move
    transfer = StaffTransfer(
        staff_user_id=staff.id, org_id=current_user.org_id,
        from_department=from_dept, to_department=payload.to_department.strip(),
        to_unit=(payload.to_unit or None), effective_date=payload.effective_date,
        reason=(payload.reason or None), created_by=current_user.id,
    )
    db.add(transfer)
    # Apply the move to the live record so the directory reflects it.
    staff.department = payload.to_department.strip()
    await db.flush()
    return _transfer_response(transfer, staff.full_name)
