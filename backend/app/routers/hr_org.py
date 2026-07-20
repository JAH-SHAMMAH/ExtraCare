"""Organization Structure router (HR Admin), prefix ``/hr``.

The org hierarchy of units (division / department / unit / team). Confidential HR
admin — gated ``hr:write``. The frontend fetches the flat list and builds the tree.

ENDPOINTS:
  GET    /hr/org-units          — all units for the org (flat; frontend nests them)
  POST   /hr/org-units          — add a unit
  PATCH  /hr/org-units/{id}     — edit / re-parent (cycle-guarded)
  DELETE /hr/org-units/{id}     — remove a leaf unit (blocked if it has children)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.hr_org import OrgUnit
from app.schemas.hr_org import OrgUnitCreate, OrgUnitUpdate, OrgUnitResponse

router = APIRouter(prefix="/hr", tags=["HR — Org Structure"])

_can_hr = Depends(PermissionChecker("hr:write"))


def _response(u: OrgUnit, head_name: str | None = None) -> OrgUnitResponse:
    return OrgUnitResponse(
        id=u.id, name=u.name, unit_type=u.unit_type, parent_id=u.parent_id,
        head_user_id=u.head_user_id, head_name=head_name, description=u.description,
        position=u.position, created_at=u.created_at, org_id=u.org_id,
    )


async def _get_owned(db: AsyncSession, org_id: str, unit_id: str) -> OrgUnit:
    u = (await db.execute(select(OrgUnit).where(
        OrgUnit.id == unit_id, OrgUnit.org_id == org_id, OrgUnit.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Org unit not found.")
    return u


async def _validate_parent(db: AsyncSession, org_id: str, node_id: str | None, parent_id: str | None):
    """Parent must exist in-org, and (for an existing node) must not be the node
    itself or one of its descendants — that would make a cycle."""
    if not parent_id:
        return
    if parent_id == node_id:
        raise HTTPException(status_code=422, detail="A unit can’t be its own parent.")
    parent = (await db.execute(select(OrgUnit).where(
        OrgUnit.id == parent_id, OrgUnit.org_id == org_id, OrgUnit.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent unit not found.")
    # Walk up from the proposed parent; if we meet node_id, it's a descendant → cycle.
    seen, cur = set(), parent
    while cur is not None:
        if node_id and cur.id == node_id:
            raise HTTPException(status_code=422, detail="That would nest a unit under its own descendant.")
        if cur.parent_id is None or cur.parent_id in seen:
            break
        seen.add(cur.id)
        cur = (await db.execute(select(OrgUnit).where(OrgUnit.id == cur.parent_id))).scalar_one_or_none()


async def _validate_head(db: AsyncSession, org_id: str, head_user_id: str | None):
    if not head_user_id:
        return
    head = (await db.execute(select(User).where(
        User.id == head_user_id, User.org_id == org_id, User.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not head:
        raise HTTPException(status_code=404, detail="Head (staff member) not found.")


async def _head_names(db: AsyncSession, units: list[OrgUnit]) -> dict[str, str]:
    ids = {u.head_user_id for u in units if u.head_user_id}
    if not ids:
        return {}
    return dict((uid, name) for uid, name in (await db.execute(
        select(User.id, User.full_name).where(User.id.in_(ids))
    )).all())


@router.get("/org-units", response_model=list[OrgUnitResponse], dependencies=[_can_hr])
async def list_units(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    units = (await db.execute(
        select(OrgUnit).where(OrgUnit.org_id == current_user.org_id, OrgUnit.is_deleted == False)  # noqa: E712
        .order_by(OrgUnit.position, OrgUnit.name)
    )).scalars().all()
    names = await _head_names(db, units)
    return [_response(u, names.get(u.head_user_id)) for u in units]


@router.post("/org-units", response_model=OrgUnitResponse, status_code=201, dependencies=[_can_hr])
async def create_unit(payload: OrgUnitCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    await _validate_parent(db, current_user.org_id, None, payload.parent_id)
    await _validate_head(db, current_user.org_id, payload.head_user_id)
    u = OrgUnit(
        name=payload.name.strip(), unit_type=(payload.unit_type or None),
        parent_id=payload.parent_id, head_user_id=payload.head_user_id,
        description=(payload.description or None), position=payload.position,
        org_id=current_user.org_id,
    )
    db.add(u)
    await db.flush()
    head = (await _head_names(db, [u])).get(u.head_user_id) if u.head_user_id else None
    return _response(u, head)


@router.patch("/org-units/{unit_id}", response_model=OrgUnitResponse, dependencies=[_can_hr])
async def update_unit(unit_id: str, payload: OrgUnitUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    u = await _get_owned(db, current_user.org_id, unit_id)
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        await _validate_parent(db, current_user.org_id, u.id, data["parent_id"])
    if "head_user_id" in data:
        await _validate_head(db, current_user.org_id, data["head_user_id"])
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for f, v in data.items():
        setattr(u, f, v)
    await db.flush()
    head = (await _head_names(db, [u])).get(u.head_user_id) if u.head_user_id else None
    return _response(u, head)


@router.delete("/org-units/{unit_id}", status_code=204, dependencies=[_can_hr])
async def delete_unit(unit_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    u = await _get_owned(db, current_user.org_id, unit_id)
    children = (await db.execute(select(func.count(OrgUnit.id)).where(
        OrgUnit.parent_id == u.id, OrgUnit.org_id == current_user.org_id, OrgUnit.is_deleted == False  # noqa: E712
    ))).scalar() or 0
    if children:
        raise HTTPException(status_code=409, detail="Move or remove this unit’s sub-units first.")
    u.is_deleted = True
    u.deleted_at = datetime.now(timezone.utc)
    await db.flush()
