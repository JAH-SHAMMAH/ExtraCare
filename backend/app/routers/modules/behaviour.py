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
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import (
    BehaviourRecord, Student,
    BehaviourCategory, BehaviourSubCategory, BehaviourLevel, BehaviourSettings,
)
from app.schemas.school_experience import BehaviourCreate, BehaviourResponse
from app.schemas.behaviour_config import (
    CategoryCreate, CategoryUpdate, CategoryResponse,
    SubCategoryCreate, SubCategoryUpdate, SubCategoryResponse,
    LevelCreate, LevelUpdate, LevelResponse,
    SettingsUpdate, SettingsResponse,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(
    prefix="/behaviour",
    tags=["Behaviour Tracker"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:behaviour:read"))
_can_write = Depends(PermissionChecker("school:behaviour:write"))


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
    request: Request = None,
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
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="BehaviourRecord", resource_id=record.id,
        resource_label=f"behaviour record for student {record.student_id}",
        metadata={"student_id": record.student_id, "type": record.type, "points": record.points},
        request=request,
    )
    return BehaviourResponse.model_validate(record).model_dump()


@router.delete("/records/{record_id}", status_code=204, dependencies=[_can_write])
async def delete_record(
    record_id: str,
    request: Request = None,
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
    rec_ref, rec_student = record.id, record.student_id
    await db.delete(record)
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="BehaviourRecord", resource_id=rec_ref,
        resource_label=f"behaviour record for student {rec_student}",
        severity="warning", request=request,
    )


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

    # Classify the student into a conduct band from their cumulative points, when
    # the org has levels defined and auto-derivation is on.
    settings = await _get_settings(db, current_user.org_id)
    level = None
    if settings.auto_derive_levels:
        levels = (await db.execute(
            select(BehaviourLevel).where(
                BehaviourLevel.org_id == current_user.org_id,
                BehaviourLevel.is_active == True,
            )
        )).scalars().all()
        level = _classify_level(levels, total_points)

    return {
        "student_id": student_id,
        "breakdown": breakdown,
        "total_points": total_points,
        "level": level,
    }


# ── Behaviour Tracker admin: taxonomy, levels, settings ──────────────────────
# Managed configuration behind the dedicated Behaviour Tracker section. All gate
# on school:behaviour (staff config); records reference the taxonomy optionally.

def _classify_level(levels, total_points: int) -> dict | None:
    """The highest band whose [min_points, max_points] contains total_points."""
    matches = [
        lv for lv in levels
        if lv.min_points <= total_points and (lv.max_points is None or total_points <= lv.max_points)
    ]
    if not matches:
        return None
    best = max(matches, key=lambda lv: lv.min_points)
    return {"id": best.id, "name": best.name, "colour": best.colour,
            "min_points": best.min_points, "max_points": best.max_points}


async def _load(db: AsyncSession, model, obj_id: str, org_id: str, label: str):
    obj = (await db.execute(
        select(model).where(model.id == obj_id, model.org_id == org_id)
    )).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{label} not found.")
    return obj


async def _get_settings(db: AsyncSession, org_id: str) -> BehaviourSettings:
    s = (await db.execute(
        select(BehaviourSettings).where(BehaviourSettings.org_id == org_id)
    )).scalar_one_or_none()
    if s is None:
        s = BehaviourSettings(org_id=org_id)
        db.add(s)
        await db.flush()
    return s


# Categories ("Manage behaviourTracker") ──────────────────────────────────────

@router.get("/categories", dependencies=[_can_read])
async def list_categories(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    rows = (await db.execute(
        select(BehaviourCategory).where(BehaviourCategory.org_id == current_user.org_id)
        .order_by(BehaviourCategory.position, BehaviourCategory.name)
    )).scalars().all()
    return {"items": [CategoryResponse.model_validate(r).model_dump() for r in rows]}


@router.post("/categories", status_code=201, dependencies=[_can_write])
async def create_category(
    payload: CategoryCreate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    cat = BehaviourCategory(**payload.model_dump(), org_id=current_user.org_id)
    db.add(cat)
    await db.flush()
    await log_action(db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourCategory", resource_id=cat.id,
                     resource_label=cat.name, request=request)
    return CategoryResponse.model_validate(cat).model_dump()


@router.patch("/categories/{category_id}", dependencies=[_can_write])
async def update_category(
    category_id: str, payload: CategoryUpdate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    cat = await _load(db, BehaviourCategory, category_id, current_user.org_id, "Category")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    await db.flush()
    await log_action(db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourCategory", resource_id=cat.id,
                     resource_label=cat.name, request=request)
    return CategoryResponse.model_validate(cat).model_dump()


@router.delete("/categories/{category_id}", status_code=204, dependencies=[_can_write])
async def delete_category(
    category_id: str, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    cat = await _load(db, BehaviourCategory, category_id, current_user.org_id, "Category")
    subs = (await db.execute(select(func.count(BehaviourSubCategory.id)).where(
        BehaviourSubCategory.category_id == category_id))).scalar()
    used = (await db.execute(select(func.count(BehaviourRecord.id)).where(
        BehaviourRecord.category_id == category_id))).scalar()
    if subs or used:
        raise HTTPException(status_code=409, detail="Category is in use (sub-categories or records). Deactivate it instead.")
    await db.delete(cat)
    await log_action(db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourCategory", resource_id=category_id,
                     resource_label=cat.name, severity="warning", request=request)


# Sub-categories ("Sub-manage behaviourTracker") ──────────────────────────────

@router.get("/subcategories", dependencies=[_can_read])
async def list_subcategories(
    category_id: str | None = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    query = select(BehaviourSubCategory).where(BehaviourSubCategory.org_id == current_user.org_id)
    if category_id:
        query = query.where(BehaviourSubCategory.category_id == category_id)
    rows = (await db.execute(
        query.order_by(BehaviourSubCategory.position, BehaviourSubCategory.name)
    )).scalars().all()
    return {"items": [SubCategoryResponse.model_validate(r).model_dump() for r in rows]}


@router.post("/subcategories", status_code=201, dependencies=[_can_write])
async def create_subcategory(
    payload: SubCategoryCreate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    # Parent category must exist in this tenant.
    await _load(db, BehaviourCategory, payload.category_id, current_user.org_id, "Category")
    sub = BehaviourSubCategory(**payload.model_dump(), org_id=current_user.org_id)
    db.add(sub)
    await db.flush()
    await log_action(db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourSubCategory", resource_id=sub.id,
                     resource_label=sub.name, request=request)
    return SubCategoryResponse.model_validate(sub).model_dump()


@router.patch("/subcategories/{sub_id}", dependencies=[_can_write])
async def update_subcategory(
    sub_id: str, payload: SubCategoryUpdate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    sub = await _load(db, BehaviourSubCategory, sub_id, current_user.org_id, "Sub-category")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("category_id"):
        await _load(db, BehaviourCategory, changes["category_id"], current_user.org_id, "Category")
    for field, value in changes.items():
        setattr(sub, field, value)
    await db.flush()
    await log_action(db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourSubCategory", resource_id=sub.id,
                     resource_label=sub.name, request=request)
    return SubCategoryResponse.model_validate(sub).model_dump()


@router.delete("/subcategories/{sub_id}", status_code=204, dependencies=[_can_write])
async def delete_subcategory(
    sub_id: str, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    sub = await _load(db, BehaviourSubCategory, sub_id, current_user.org_id, "Sub-category")
    used = (await db.execute(select(func.count(BehaviourRecord.id)).where(
        BehaviourRecord.subcategory_id == sub_id))).scalar()
    if used:
        raise HTTPException(status_code=409, detail="Sub-category is in use by records. Deactivate it instead.")
    await db.delete(sub)
    await log_action(db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourSubCategory", resource_id=sub_id,
                     resource_label=sub.name, severity="warning", request=request)


# Levels ("Manage behaviour levels") ──────────────────────────────────────────

@router.get("/levels", dependencies=[_can_read])
async def list_levels(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    rows = (await db.execute(
        select(BehaviourLevel).where(BehaviourLevel.org_id == current_user.org_id)
        .order_by(BehaviourLevel.position, BehaviourLevel.min_points)
    )).scalars().all()
    return {"items": [LevelResponse.model_validate(r).model_dump() for r in rows]}


@router.post("/levels", status_code=201, dependencies=[_can_write])
async def create_level(
    payload: LevelCreate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    if payload.max_points is not None and payload.max_points < payload.min_points:
        raise HTTPException(status_code=422, detail="max_points must be ≥ min_points.")
    lv = BehaviourLevel(**payload.model_dump(), org_id=current_user.org_id)
    db.add(lv)
    await db.flush()
    await log_action(db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourLevel", resource_id=lv.id,
                     resource_label=lv.name, request=request)
    return LevelResponse.model_validate(lv).model_dump()


@router.patch("/levels/{level_id}", dependencies=[_can_write])
async def update_level(
    level_id: str, payload: LevelUpdate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    lv = await _load(db, BehaviourLevel, level_id, current_user.org_id, "Level")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lv, field, value)
    if lv.max_points is not None and lv.max_points < lv.min_points:
        raise HTTPException(status_code=422, detail="max_points must be ≥ min_points.")
    await db.flush()
    await log_action(db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourLevel", resource_id=lv.id,
                     resource_label=lv.name, request=request)
    return LevelResponse.model_validate(lv).model_dump()


@router.delete("/levels/{level_id}", status_code=204, dependencies=[_can_write])
async def delete_level(
    level_id: str, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    lv = await _load(db, BehaviourLevel, level_id, current_user.org_id, "Level")
    await db.delete(lv)
    await log_action(db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourLevel", resource_id=level_id,
                     resource_label=lv.name, severity="warning", request=request)


# Settings ("BehaviourTracker settings") ──────────────────────────────────────

@router.get("/settings", dependencies=[_can_read])
async def get_settings(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    s = await _get_settings(db, current_user.org_id)
    return SettingsResponse.model_validate(s).model_dump()


@router.put("/settings", dependencies=[_can_write])
async def update_settings(
    payload: SettingsUpdate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    s = await _get_settings(db, current_user.org_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await db.flush()
    await log_action(db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
                     resource_type="BehaviourSettings", resource_id=s.id,
                     resource_label="behaviour settings", request=request)
    return SettingsResponse.model_validate(s).model_dump()
