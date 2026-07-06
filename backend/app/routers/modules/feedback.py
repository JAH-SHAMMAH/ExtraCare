"""
Feedback Router
================
Student-to-school feedback channel with an admin resolution workflow.

Design notes:
  - Any authenticated user of the school module can submit feedback
    (school:read suffices — this is a self-service endpoint that writes a
    user's own message, not an administrative write).
  - Only users with school:write (typically teachers/admins) can resolve and
    respond to feedback. This mirrors how business:leave handles self-service
    submission vs. managerial review.

RBAC:
  - school:read   → submit, list own
  - school:write  → list all, resolve, respond
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import StudentFeedback
from app.schemas.school_experience import (
    FeedbackCreate,
    FeedbackResolve,
    FeedbackResponse,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:feedback:read"))
_can_write = Depends(PermissionChecker("school:feedback:write"))


@router.post("", status_code=201, dependencies=[_can_read])
async def submit_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    feedback = StudentFeedback(
        **payload.model_dump(),
        submitted_by=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(feedback)
    await db.flush()
    return FeedbackResponse.model_validate(feedback).model_dump()


@router.get("", dependencies=[_can_read])
async def list_feedback(
    mine: bool = False,
    category: str | None = None,
    resolved: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(StudentFeedback).where(StudentFeedback.org_id == current_user.org_id)

    # Self-service: students see only their own submissions. Admin listing is
    # gated behind school:write (see list_all below) — keeping this endpoint
    # scoped prevents students from reading each other's feedback.
    if mine or not current_user.has_permission("school:write"):
        query = query.where(StudentFeedback.submitted_by == current_user.id)

    if category:
        query = query.where(StudentFeedback.category == category)
    if resolved is not None:
        query = query.where(StudentFeedback.is_resolved == resolved)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(StudentFeedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    # Anonymous submissions hide the submitter id for non-admin viewers.
    response_items = []
    for f in items:
        data = FeedbackResponse.model_validate(f).model_dump()
        if f.is_anonymous and not current_user.has_permission("school:write"):
            data["submitted_by"] = None
        response_items.append(data)

    return {
        "items": response_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{feedback_id}/resolve", dependencies=[_can_write])
async def resolve_feedback(
    feedback_id: str,
    payload: FeedbackResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(StudentFeedback).where(
            StudentFeedback.id == feedback_id,
            StudentFeedback.org_id == current_user.org_id,
        )
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found.")

    feedback.admin_response = payload.admin_response
    feedback.is_resolved = payload.is_resolved
    feedback.responded_by = current_user.id
    feedback.responded_at = datetime.now(timezone.utc)
    await db.flush()
    return FeedbackResponse.model_validate(feedback).model_dump()
