"""Which classes a staff member may act on.

Admins (and the Super User) -> None (no restriction). Everyone else -> the set of
class ids they are class teacher of, assistant of, or teach through a Teaching
Assignment / timetable slot."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.modules.school import SchoolClass


async def teacher_class_scope(db: AsyncSession, user: User) -> set[str] | None:
    if user.is_superadmin or user.has_permission("school_admin:read"):
        return None
    from app.models.modules.platform import ClassAssistant
    from app.routers.modules.platform import _teacher_assignments
    org = user.org_id
    ids = set((await db.execute(select(SchoolClass.id).where(
        SchoolClass.org_id == org, SchoolClass.teacher_id == user.id))).scalars().all())
    ids |= set((await db.execute(select(ClassAssistant.class_id).where(
        ClassAssistant.org_id == org, ClassAssistant.teacher_id == user.id))).scalars().all())
    ids |= {c for c, _ in await _teacher_assignments(db, org, user.id)}
    return ids


def require_class(scope: set[str] | None, class_id: str | None, what: str = "mark attendance for") -> None:
    if scope is not None and (not class_id or class_id not in scope):
        raise HTTPException(status_code=403, detail=f"You can only {what} classes you teach.")
