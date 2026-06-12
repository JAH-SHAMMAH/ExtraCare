"""
Behaviour Tracker (Pastoral Care) Router
==========================================
Positive and negative behaviour records, visible to teachers and admins.
Students view their own history via a scoped endpoint.

RBAC:
  - school:read   → view records (admins/teachers broad, students should go
                    through the scoped /student/{id} endpoint)
  - school:write  → add / edit / delete records
"""

from datetime import date as date_type, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import BehaviourRecord, Student
from app.schemas.school_experience import BehaviourCreate, BehaviourResponse
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker

router = APIRouter(
    prefix="/behaviour",
    tags=["Behaviour Tracker"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:read"))
_can_write = Depends(PermissionChecker("school:write"))


@router.get("/records", dependencies=[_can_read])
async def list_records(
    student_id: str | None = None,
    type_filter: str | None = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(BehaviourRecord).where(BehaviourRecord.org_id == current_user.org_id)
    if student_id:
        query = query.where(BehaviourRecord.student_id == student_id)
    if type_filter:
        query = query.where(BehaviourRecord.type == type_filter)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(BehaviourRecord.incident_date.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return {
        "items": [BehaviourResponse.model_validate(r).model_dump() for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/records", status_code=201, dependencies=[_can_write])
async def create_record(
    payload: BehaviourCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Verify student exists in this tenant
    student = (await db.execute(
        select(Student).where(
            Student.id == payload.student_id,
            Student.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    record = BehaviourRecord(
        **payload.model_dump(),
        recorded_by=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(record)
    await db.flush()
    return BehaviourResponse.model_validate(record).model_dump()


@router.delete("/records/{record_id}", status_code=204, dependencies=[_can_write])
async def delete_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(BehaviourRecord).where(
            BehaviourRecord.id == record_id,
            BehaviourRecord.org_id == current_user.org_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    await db.delete(record)


@router.get("/summary", dependencies=[_can_read])
async def school_summary(
    response: Response,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """School-wide breakdown for the admin behaviour widget."""
    # Rolling 30-day aggregate — moves slowly, short private cache is safe.
    response.headers["Cache-Control"] = "private, max-age=30"
    cutoff = (datetime.now(timezone.utc).date()) - timedelta(days=days)

    # Counts and points by type
    type_rows = (await db.execute(
        select(
            BehaviourRecord.type,
            func.count(BehaviourRecord.id).label("count"),
            func.coalesce(func.sum(BehaviourRecord.points), 0).label("points"),
        ).where(
            BehaviourRecord.org_id == current_user.org_id,
            BehaviourRecord.incident_date >= cutoff,
        ).group_by(BehaviourRecord.type)
    )).all()

    breakdown = {"positive": {"count": 0, "points": 0}, "negative": {"count": 0, "points": 0}, "neutral": {"count": 0, "points": 0}}
    total_points = 0
    total_count = 0
    for row in type_rows:
        key = row.type.value if hasattr(row.type, "value") else row.type
        breakdown[key] = {"count": row.count, "points": int(row.points or 0)}
        total_points += int(row.points or 0)
        total_count += row.count

    # Top categories
    cat_rows = (await db.execute(
        select(
            BehaviourRecord.category,
            func.count(BehaviourRecord.id).label("count"),
        ).where(
            BehaviourRecord.org_id == current_user.org_id,
            BehaviourRecord.incident_date >= cutoff,
            BehaviourRecord.category.isnot(None),
        ).group_by(BehaviourRecord.category)
        .order_by(func.count(BehaviourRecord.id).desc())
        .limit(5)
    )).all()

    return {
        "days": days,
        "since": cutoff.isoformat(),
        "total_count": total_count,
        "total_points": total_points,
        "breakdown": breakdown,
        "top_categories": [{"category": r.category, "count": r.count} for r in cat_rows],
    }


@router.get("/student/{student_id}/summary", dependencies=[_can_read])
async def student_summary(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Aggregate points + counts by type for a given student."""
    result = await db.execute(
        select(
            BehaviourRecord.type,
            func.count(BehaviourRecord.id).label("count"),
            func.coalesce(func.sum(BehaviourRecord.points), 0).label("total_points"),
        ).where(
            BehaviourRecord.student_id == student_id,
            BehaviourRecord.org_id == current_user.org_id,
        ).group_by(BehaviourRecord.type)
    )

    breakdown = {}
    total_points = 0
    for row in result:
        key = row.type.value if hasattr(row.type, "value") else row.type
        breakdown[key] = {"count": row.count, "points": row.total_points}
        total_points += row.total_points

    return {
        "student_id": student_id,
        "breakdown": breakdown,
        "total_points": total_points,
    }
