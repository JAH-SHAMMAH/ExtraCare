"""Parents Directory router (People & HR, Batch 1).

A staff-side directory over the existing ``ParentGuardian`` link table: who
guards which student, the relationship, and the primary contact flag. Lets the
office search, link, re-label, and unlink guardians without touching the
free-text guardian fields kept on ``Student`` for imports.

RBAC
----
  school:parents:read   → view the directory (staff roles; via the broad-grant
                          hierarchy a teacher's ``school:read`` covers it). Not
                          held by students/parents, so it stays staff-only.
  school:parents:write  → link / relabel / unlink guardians.

Every query is pinned to ``current_user.org_id`` for tenant isolation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.modules.school import ParentGuardian, Student
from app.schemas.people import (
    ParentLinkCreate, ParentLinkUpdate, ParentLinkResponse, ParentLinkListResponse,
    ParentSummary, GuardedStudentSummary,
)
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(
    prefix="/school/parents",
    tags=["Parents Directory"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:parents:read"))
_can_write = Depends(PermissionChecker("school:parents:write"))

_RELATIONSHIPS = {"parent", "guardian", "other"}


def _to_response(link: ParentGuardian) -> ParentLinkResponse:
    u = link.user
    s = link.student
    cls = s.school_class if s else None
    return ParentLinkResponse(
        id=link.id,
        relationship_type=link.relationship_type or "parent",
        is_primary=bool(link.is_primary),
        parent=ParentSummary(
            id=u.id, full_name=u.full_name, email=u.email, phone=getattr(u, "phone", None),
        ),
        student=GuardedStudentSummary(
            id=s.id,
            student_id=s.student_id,
            full_name=f"{s.first_name} {s.last_name}".strip(),
            class_name=cls.name if cls else None,
        ),
        created_at=link.created_at,
        org_id=link.org_id,
    )


async def _load_link(db: AsyncSession, link_id: str, org_id: str) -> ParentGuardian:
    link = (await db.execute(
        select(ParentGuardian)
        .options(
            selectinload(ParentGuardian.user),
            selectinload(ParentGuardian.student).selectinload(Student.school_class),
        )
        .where(ParentGuardian.id == link_id, ParentGuardian.org_id == org_id)
    )).scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Guardian link not found.")
    return link


@router.get("", response_model=ParentLinkListResponse, dependencies=[_can_read])
async def list_parent_links(
    search: str | None = Query(default=None, description="Filter by parent name/email or student name/id."),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = (
        select(ParentGuardian)
        .join(User, User.id == ParentGuardian.user_id)
        .join(Student, Student.id == ParentGuardian.student_id)
        .where(ParentGuardian.org_id == current_user.org_id)
    )
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        base = base.where(or_(
            func.lower(User.full_name).like(term),
            func.lower(User.email).like(term),
            func.lower(Student.first_name).like(term),
            func.lower(Student.last_name).like(term),
            func.lower(Student.student_id).like(term),
        ))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    rows = (await db.execute(
        base.options(
            selectinload(ParentGuardian.user),
            selectinload(ParentGuardian.student).selectinload(Student.school_class),
        )
        .order_by(ParentGuardian.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return ParentLinkListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ParentLinkResponse, status_code=201, dependencies=[_can_write])
async def create_parent_link(
    payload: ParentLinkCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.relationship_type not in _RELATIONSHIPS:
        raise HTTPException(status_code=422, detail=f"relationship_type must be one of {sorted(_RELATIONSHIPS)}")

    parent = (await db.execute(
        select(User).where(
            User.id == payload.user_id,
            User.org_id == current_user.org_id,
            User.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="user_id: parent user not found in your organisation.")

    student = (await db.execute(
        select(Student).where(
            Student.id == payload.student_id,
            Student.org_id == current_user.org_id,
            Student.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="student_id: student not found in your organisation.")

    link = ParentGuardian(
        user_id=parent.id,
        student_id=student.id,
        relationship_type=payload.relationship_type,
        is_primary=payload.is_primary,
        org_id=current_user.org_id,
    )
    db.add(link)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This guardian is already linked to that student.")

    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="ParentGuardian", resource_id=link.id,
        resource_label=f"guardian link {parent.full_name} → {student.first_name} {student.last_name}",
        metadata={"user_id": parent.id, "student_id": student.id, "relationship_type": link.relationship_type},
        request=request,
    )
    return _to_response(await _load_link(db, link.id, current_user.org_id))


@router.patch("/{link_id}", response_model=ParentLinkResponse, dependencies=[_can_write])
async def update_parent_link(
    link_id: str,
    payload: ParentLinkUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    link = await _load_link(db, link_id, current_user.org_id)

    if payload.relationship_type is not None:
        if payload.relationship_type not in _RELATIONSHIPS:
            raise HTTPException(status_code=422, detail=f"relationship_type must be one of {sorted(_RELATIONSHIPS)}")
        link.relationship_type = payload.relationship_type
    if payload.is_primary is not None:
        link.is_primary = payload.is_primary

    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="ParentGuardian", resource_id=link.id,
        resource_label="guardian link", request=request,
    )
    return _to_response(await _load_link(db, link.id, current_user.org_id))


@router.delete("/{link_id}", status_code=204, dependencies=[_can_write])
async def delete_parent_link(
    link_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    link = await _load_link(db, link_id, current_user.org_id)
    ref = link.id
    await db.delete(link)
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="ParentGuardian", resource_id=ref,
        resource_label="guardian link", severity="warning", request=request,
    )
