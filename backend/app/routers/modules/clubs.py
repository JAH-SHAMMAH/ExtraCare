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
from app.models.modules.school import (
    Club, ClubMembership, Student,
    ClubSettings, ClubGrade, ClubCoordinator, ClubEnrollmentDeadline,
)
from app.schemas.school_experience import (
    ClubCreate,
    ClubUpdate,
    ClubResponse,
    ClubJoin,
    ClubMembershipResponse,
    ClubSettingsResponse,
    ClubSettingsUpdate,
    ClubGradeCreate,
    ClubGradeUpdate,
    ClubGradeResponse,
    ClubCoordinatorCreate,
    ClubCoordinatorResponse,
    ClubDeadlineCreate,
    ClubDeadlineResponse,
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


# ── Manage Clubs: Settings ────────────────────────────────────────────────────
# NOTE: these specific routes MUST precede "/{club_id}" so they aren't captured
# by the club-id path parameter.

async def _get_or_create_club_settings(db: AsyncSession, org_id: str) -> ClubSettings:
    s = (await db.execute(select(ClubSettings).where(ClubSettings.org_id == org_id))).scalar_one_or_none()
    if not s:
        s = ClubSettings(org_id=org_id)
        db.add(s)
        await db.flush()
    return s


@router.get("/settings", dependencies=[_can_read])
async def get_club_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_or_create_club_settings(db, current_user.org_id)
    return ClubSettingsResponse.model_validate(s).model_dump()


@router.put("/settings", dependencies=[_can_write])
async def update_club_settings(payload: ClubSettingsUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_or_create_club_settings(db, current_user.org_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await db.flush()
    return ClubSettingsResponse.model_validate(s).model_dump()


# ── Manage Clubs: Grades ──────────────────────────────────────────────────────

@router.get("/grades", dependencies=[_can_read])
async def list_club_grades(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(ClubGrade).where(ClubGrade.org_id == current_user.org_id).order_by(ClubGrade.grade_letter))).scalars().all()
    return {"items": [ClubGradeResponse.model_validate(g).model_dump() for g in rows]}


@router.post("/grades", status_code=201, dependencies=[_can_write])
async def create_club_grade(payload: ClubGradeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    g = ClubGrade(**payload.model_dump(), org_id=current_user.org_id)
    db.add(g)
    await db.flush()
    return ClubGradeResponse.model_validate(g).model_dump()


@router.patch("/grades/{grade_id}", dependencies=[_can_write])
async def update_club_grade(grade_id: str, payload: ClubGradeUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    g = (await db.execute(select(ClubGrade).where(ClubGrade.id == grade_id, ClubGrade.org_id == current_user.org_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grade not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(g, field, value)
    await db.flush()
    return ClubGradeResponse.model_validate(g).model_dump()


@router.delete("/grades/{grade_id}", status_code=204, dependencies=[_can_write])
async def delete_club_grade(grade_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    g = (await db.execute(select(ClubGrade).where(ClubGrade.id == grade_id, ClubGrade.org_id == current_user.org_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grade not found.")
    await db.delete(g)


# ── Manage Clubs: Coordinators ────────────────────────────────────────────────

@router.get("/coordinators", dependencies=[_can_read])
async def list_club_coordinators(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(ClubCoordinator, User.full_name, Club.name)
        .join(User, User.id == ClubCoordinator.coordinator_id)
        .join(Club, Club.id == ClubCoordinator.club_id)
        .where(ClubCoordinator.org_id == current_user.org_id)
        .order_by(User.full_name)
    )).all()
    items = []
    for c, cname, club_name in rows:
        d = ClubCoordinatorResponse.model_validate(c).model_dump()
        d["coordinator_name"] = cname
        d["club_name"] = club_name
        items.append(d)
    return {"items": items}


@router.post("/coordinators", status_code=201, dependencies=[_can_write])
async def create_club_coordinator(payload: ClubCoordinatorCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    club = await _get_club_or_404(db, payload.club_id, current_user.org_id)
    user = (await db.execute(select(User).where(User.id == payload.coordinator_id, User.org_id == current_user.org_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Coordinator (staff) not found in your organisation.")
    dup = (await db.execute(select(ClubCoordinator).where(
        ClubCoordinator.org_id == current_user.org_id,
        ClubCoordinator.coordinator_id == payload.coordinator_id,
        ClubCoordinator.club_id == payload.club_id))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="That coordinator is already assigned to this club.")
    c = ClubCoordinator(coordinator_id=payload.coordinator_id, club_id=payload.club_id, org_id=current_user.org_id)
    db.add(c)
    await db.flush()
    d = ClubCoordinatorResponse.model_validate(c).model_dump()
    d["coordinator_name"] = user.full_name
    d["club_name"] = club.name
    return d


@router.delete("/coordinators/{coordinator_row_id}", status_code=204, dependencies=[_can_write])
async def delete_club_coordinator(coordinator_row_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(ClubCoordinator).where(ClubCoordinator.id == coordinator_row_id, ClubCoordinator.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Coordinator assignment not found.")
    await db.delete(c)


# ── Manage Clubs: Enrollment deadlines ────────────────────────────────────────

@router.get("/deadlines", dependencies=[_can_read])
async def list_club_deadlines(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(ClubEnrollmentDeadline).where(ClubEnrollmentDeadline.org_id == current_user.org_id).order_by(ClubEnrollmentDeadline.deadline.desc()))).scalars().all()
    return {"items": [ClubDeadlineResponse.model_validate(d).model_dump() for d in rows]}


@router.post("/deadlines", status_code=201, dependencies=[_can_write])
async def create_club_deadline(payload: ClubDeadlineCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = ClubEnrollmentDeadline(**payload.model_dump(), org_id=current_user.org_id)
    db.add(d)
    await db.flush()
    return ClubDeadlineResponse.model_validate(d).model_dump()


@router.delete("/deadlines/{deadline_id}", status_code=204, dependencies=[_can_write])
async def delete_club_deadline(deadline_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = (await db.execute(select(ClubEnrollmentDeadline).where(ClubEnrollmentDeadline.id == deadline_id, ClubEnrollmentDeadline.org_id == current_user.org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Deadline not found.")
    await db.delete(d)


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
