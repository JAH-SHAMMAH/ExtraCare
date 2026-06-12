"""
Photo Journals + Weekly Remarks Router
========================================
Two closely related features bundled into one router:

  - Photo Journals: timestamped photo posts with tags, optionally tied to a
    class or club. Teachers/admins post; everyone in the school can view.
  - Weekly Remarks: short teacher-written notes about a student's week,
    visible to the student and to school admins.

RBAC:
  - school:read   → view journals, view remarks (students see their own)
  - school:write  → create / update / delete
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import PhotoJournal, WeeklyRemark, Student
from app.schemas.school_experience import (
    JournalCreate,
    JournalResponse,
    RemarkCreate,
    RemarkResponse,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.core.school_identity import resolve_linked_student_id

router = APIRouter(
    prefix="/journals",
    tags=["Photo Journals & Weekly Remarks"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:read"))
_can_write = Depends(PermissionChecker("school:write"))


# ── Photo Journals ────────────────────────────────────────────────────────────


@router.get("", dependencies=[_can_read])
async def list_journals(
    class_id: str | None = None,
    club_id: str | None = None,
    tag: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(PhotoJournal).where(
        PhotoJournal.org_id == current_user.org_id,
        PhotoJournal.is_deleted == False,
    )
    if class_id:
        query = query.where(PhotoJournal.class_id == class_id)
    if club_id:
        query = query.where(PhotoJournal.club_id == club_id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(PhotoJournal.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    # Tag filter is applied in Python because JSON array membership is
    # inconsistent across dialects. The volume here is expected to be small.
    if tag:
        items = [j for j in items if tag in (j.tags or [])]

    return {
        "items": [JournalResponse.model_validate(j).model_dump() for j in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", status_code=201, dependencies=[_can_write])
async def create_journal(
    payload: JournalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    journal = PhotoJournal(
        **payload.model_dump(),
        posted_by=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(journal)
    await db.flush()
    return JournalResponse.model_validate(journal).model_dump()


@router.delete("/{journal_id}", status_code=204, dependencies=[_can_write])
async def delete_journal(
    journal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(PhotoJournal).where(
            PhotoJournal.id == journal_id,
            PhotoJournal.org_id == current_user.org_id,
        )
    )
    journal = result.scalar_one_or_none()
    if not journal:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    journal.is_deleted = True


# ── Weekly Remarks ────────────────────────────────────────────────────────────


@router.get("/remarks", dependencies=[_can_read])
async def list_remarks(
    student_id: str | None = None,
    week_start: str | None = None,
    for_me: bool = Query(default=False, description="Student → own remarks. Teacher → remarks they wrote."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(WeeklyRemark).where(WeeklyRemark.org_id == current_user.org_id)
    if student_id:
        query = query.where(WeeklyRemark.student_id == student_id)
    if week_start:
        query = query.where(WeeklyRemark.week_start == week_start)
    if for_me:
        # Teachers with school:write see their own authored remarks; others fall
        # back to the student-linked filter.
        if current_user.has_permission("school:write"):
            query = query.where(WeeklyRemark.teacher_id == current_user.id)
        else:
            linked = await resolve_linked_student_id(db, current_user)
            query = query.where(WeeklyRemark.student_id == (linked or "__none__"))
    query = query.order_by(WeeklyRemark.week_start.desc())
    items = (await db.execute(query)).scalars().all()
    return {"items": [RemarkResponse.model_validate(r).model_dump() for r in items]}


@router.post("/remarks", status_code=201, dependencies=[_can_write])
async def create_remark(
    payload: RemarkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Verify student in tenant
    student = (await db.execute(
        select(Student).where(
            Student.id == payload.student_id,
            Student.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    remark = WeeklyRemark(
        **payload.model_dump(),
        teacher_id=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(remark)
    await db.flush()
    return RemarkResponse.model_validate(remark).model_dump()


@router.delete("/remarks/{remark_id}", status_code=204, dependencies=[_can_write])
async def delete_remark(
    remark_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(WeeklyRemark).where(
            WeeklyRemark.id == remark_id,
            WeeklyRemark.org_id == current_user.org_id,
        )
    )
    remark = result.scalar_one_or_none()
    if not remark:
        raise HTTPException(status_code=404, detail="Remark not found.")
    await db.delete(remark)
