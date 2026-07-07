"""Global search — cross-entity typeahead for the top-bar search box.

RBAC-aware: the box renders for every user, so each bucket only returns rows the
caller may read (a parent/student holding neither school nor user scopes gets an
empty list, never a peer's data). Returns a flat {items: [{module, label,
sublabel}]} that the frontend groups + routes by `module`.
"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import Student

_logger = logging.getLogger("extracare.search")
router = APIRouter(prefix="/search", tags=["Search"])

_PER_BUCKET = 6


@router.get("")
async def global_search(
    q: str = Query(min_length=2, max_length=100),
    modules: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    wanted = {m.strip() for m in modules.split(",") if m.strip()} if modules else None
    org_id = current_user.org_id
    term = f"%{q}%"
    items: list[dict] = []

    # Students — school read scope (school:read satisfies school:students:read).
    if (not wanted or "students" in wanted) and current_user.has_permission("school:students:read"):
        rows = (await db.execute(
            select(Student).where(
                Student.org_id == org_id, Student.is_deleted == False,  # noqa: E712
                or_(Student.first_name.ilike(term), Student.last_name.ilike(term),
                    Student.student_id.ilike(term), Student.email.ilike(term)))
            .order_by(Student.first_name).limit(_PER_BUCKET)
        )).scalars().all()
        for s in rows:
            name = " ".join(p for p in [s.first_name, s.last_name] if p) or s.student_id
            items.append({"module": "students", "label": name, "sublabel": s.student_id})

    # Users (staff, incl. teachers) — org user-management scope.
    if (not wanted or wanted & {"users", "teachers"}) and current_user.has_permission("users:read"):
        rows = (await db.execute(
            select(User).where(
                User.org_id == org_id,
                or_(User.full_name.ilike(term), User.email.ilike(term)))
            .order_by(User.full_name).limit(_PER_BUCKET)
        )).scalars().all()
        for u in rows:
            items.append({"module": "users", "label": u.full_name or u.email, "sublabel": u.email})

    return {"items": items, "query": q}
