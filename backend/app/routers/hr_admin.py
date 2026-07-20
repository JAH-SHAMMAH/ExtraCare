"""HR Admin managed lists router (Phase 1), prefix ``/hr``.

The Educare 'Admin › Job' cluster — seven managed lists (Job Titles, Job
Categories, Pay Grades, Salary Components, Work Shifts, Employment Status,
Working Tools) behind one generic table. Confidential HR admin: every endpoint
is gated ``hr:write`` so hr:read-only roles (teachers/staff) never see them.

ENDPOINTS:
  GET    /hr/admin/lists                 — catalog + live counts (Admin overview)
  GET    /hr/admin/lists/{list_type}     — items in one list (?include_inactive)
  POST   /hr/admin/lists/{list_type}     — add an item
  PATCH  /hr/admin/items/{item_id}       — edit an item
  DELETE /hr/admin/items/{item_id}       — soft-delete an item
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.hr_admin import HrManagedItem, HR_LIST_TYPES
from app.schemas.hr_admin import HrItemCreate, HrItemUpdate, HrItemResponse, HrListSummary

router = APIRouter(prefix="/hr", tags=["HR — Admin lists"])

_can_hr = Depends(PermissionChecker("hr:write"))


def _valid_list_type(list_type: str) -> str:
    if list_type not in HR_LIST_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown HR list '{list_type}'.")
    return list_type


def _response(it: HrManagedItem) -> HrItemResponse:
    return HrItemResponse(
        id=it.id, list_type=it.list_type, name=it.name, code=it.code,
        description=it.description, sort_order=it.sort_order, is_active=it.is_active,
        created_at=it.created_at, org_id=it.org_id,
    )


@router.get("/admin/lists", response_model=list[HrListSummary], dependencies=[_can_hr])
async def list_catalog(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Every Phase-1 list with its live (non-deleted) item count, for the Admin overview."""
    rows = dict((lt, c) for lt, c in (await db.execute(
        select(HrManagedItem.list_type, func.count(HrManagedItem.id)).where(
            HrManagedItem.org_id == current_user.org_id, HrManagedItem.is_deleted == False,  # noqa: E712
        ).group_by(HrManagedItem.list_type)
    )).all())
    return [HrListSummary(list_type=lt, label=label, count=rows.get(lt, 0)) for lt, label in HR_LIST_TYPES.items()]


@router.get("/admin/lists/{list_type}", response_model=list[HrItemResponse], dependencies=[_can_hr])
async def list_items(
    list_type: str,
    include_inactive: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _valid_list_type(list_type)
    q = select(HrManagedItem).where(
        HrManagedItem.org_id == current_user.org_id,
        HrManagedItem.list_type == list_type,
        HrManagedItem.is_deleted == False,  # noqa: E712
    )
    if not include_inactive:
        q = q.where(HrManagedItem.is_active == True)  # noqa: E712
    rows = (await db.execute(q.order_by(HrManagedItem.sort_order, HrManagedItem.name))).scalars().all()
    return [_response(it) for it in rows]


@router.post("/admin/lists/{list_type}", response_model=HrItemResponse, status_code=201, dependencies=[_can_hr])
async def create_item(
    list_type: str,
    payload: HrItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _valid_list_type(list_type)
    it = HrManagedItem(
        list_type=list_type,
        name=payload.name.strip(),
        code=(payload.code or None),
        description=(payload.description or None),
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        org_id=current_user.org_id,
    )
    db.add(it)
    await db.flush()
    return _response(it)


async def _get_owned(item_id: str, db: AsyncSession, current_user: User) -> HrManagedItem:
    it = (await db.execute(select(HrManagedItem).where(
        HrManagedItem.id == item_id,
        HrManagedItem.org_id == current_user.org_id,
        HrManagedItem.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if not it:
        raise HTTPException(status_code=404, detail="Item not found.")
    return it


@router.patch("/admin/items/{item_id}", response_model=HrItemResponse, dependencies=[_can_hr])
async def update_item(
    item_id: str,
    payload: HrItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    it = await _get_owned(item_id, db, current_user)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for f, v in data.items():
        setattr(it, f, v)
    await db.flush()
    return _response(it)


@router.delete("/admin/items/{item_id}", status_code=204, dependencies=[_can_hr])
async def delete_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    it = await _get_owned(item_id, db, current_user)
    it.is_deleted = True
    it.deleted_at = datetime.now(timezone.utc)
    await db.flush()
