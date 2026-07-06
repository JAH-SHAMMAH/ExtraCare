"""
Clubs & Activities Router
===========================
Clubs represent extracurricular activities students can join. Teachers act as
advisors; students become members through explicit join calls.

RBAC:
  - school:read   → list clubs, view members, students listing their memberships
  - school:write  → create / update / add members / remove members
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import Club, ClubMembership, Student
from app.schemas.school_experience import (
    ClubCreate,
    ClubUpdate,
    ClubResponse,
    ClubJoin,
    ClubMembershipResponse,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker

router = APIRouter(
    prefix="/clubs",
    tags=["Clubs & Activities"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:clubs:read"))
_can_write = Depends(PermissionChecker("school:clubs:write"))


@router.get("", dependencies=[_can_read])
async def list_clubs(
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Club).where(
        Club.org_id == current_user.org_id,
        Club.is_deleted == False,
    )
    if is_active is not None:
        query = query.where(Club.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(Club.name.asc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    # Enrich with member counts — one query for the full batch is cheaper
    # than N+1 selects on the detail view.
    ids = [c.id for c in items]
    counts_by_club: dict[str, int] = {}
    if ids:
        count_rows = await db.execute(
            select(ClubMembership.club_id, func.count(ClubMembership.id))
            .where(
                ClubMembership.club_id.in_(ids),
                ClubMembership.org_id == current_user.org_id,
                ClubMembership.is_active == True,
            )
            .group_by(ClubMembership.club_id)
        )
        counts_by_club = {row[0]: row[1] for row in count_rows}

    enriched = []
    for club in items:
        data = ClubResponse.model_validate(club).model_dump()
        data["member_count"] = counts_by_club.get(club.id, 0)
        enriched.append(data)

    return {
        "items": enriched,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", status_code=201, dependencies=[_can_write])
async def create_club(
    payload: ClubCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = Club(**payload.model_dump(), org_id=current_user.org_id)
    db.add(club)
    await db.flush()
    return ClubResponse.model_validate(club).model_dump()


@router.get("/{club_id}", dependencies=[_can_read])
async def get_club(
    club_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = await _get_club_or_404(db, club_id, current_user.org_id)
    return ClubResponse.model_validate(club).model_dump()


@router.patch("/{club_id}", dependencies=[_can_write])
async def update_club(
    club_id: str,
    payload: ClubUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = await _get_club_or_404(db, club_id, current_user.org_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(club, field, value)
    await db.flush()
    return ClubResponse.model_validate(club).model_dump()


@router.delete("/{club_id}", status_code=204, dependencies=[_can_write])
async def delete_club(
    club_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = await _get_club_or_404(db, club_id, current_user.org_id)
    club.is_deleted = True
    club.is_active = False
    club.deleted_at = datetime.now(timezone.utc)


# ── Memberships ───────────────────────────────────────────────────────────────


@router.get("/{club_id}/members", dependencies=[_can_read])
async def list_members(
    club_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_club_or_404(db, club_id, current_user.org_id)
    result = await db.execute(
        select(ClubMembership).where(
            ClubMembership.club_id == club_id,
            ClubMembership.org_id == current_user.org_id,
            ClubMembership.is_active == True,
        )
    )
    members = result.scalars().all()
    return {"items": [ClubMembershipResponse.model_validate(m).model_dump() for m in members]}


@router.post("/{club_id}/join", status_code=201, dependencies=[_can_write])
async def add_member(
    club_id: str,
    payload: ClubJoin,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = await _get_club_or_404(db, club_id, current_user.org_id)

    # Verify student is in this tenant
    student = (await db.execute(
        select(Student).where(
            Student.id == payload.student_id,
            Student.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    # Capacity check
    if club.max_members:
        existing_count = (await db.execute(
            select(func.count(ClubMembership.id)).where(
                ClubMembership.club_id == club.id,
                ClubMembership.is_active == True,
            )
        )).scalar()
        if existing_count >= club.max_members:
            raise HTTPException(status_code=400, detail="Club is full.")

    # Prevent duplicate active memberships
    dup = (await db.execute(
        select(ClubMembership).where(
            ClubMembership.club_id == club.id,
            ClubMembership.student_id == payload.student_id,
            ClubMembership.is_active == True,
        )
    )).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=400, detail="Student is already a member.")

    membership = ClubMembership(
        club_id=club.id,
        student_id=payload.student_id,
        role=payload.role,
        org_id=current_user.org_id,
    )
    db.add(membership)
    await db.flush()
    return ClubMembershipResponse.model_validate(membership).model_dump()


@router.delete("/memberships/{membership_id}", status_code=204, dependencies=[_can_write])
async def remove_member(
    membership_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(ClubMembership).where(
            ClubMembership.id == membership_id,
            ClubMembership.org_id == current_user.org_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found.")
    membership.is_active = False


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_club_or_404(db: AsyncSession, club_id: str, org_id: str) -> Club:
    result = await db.execute(
        select(Club).where(
            Club.id == club_id,
            Club.org_id == org_id,
            Club.is_deleted == False,
        )
    )
    club = result.scalar_one_or_none()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found.")
    return club
