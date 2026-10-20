"""Which roles are TEACHING roles — the ones that must belong to a school section.

A teacher's section (Early Years / Primary / Secondary) decides which report menus
they see and which pupils' data they can reach, so an account created with a
teaching role and no section would show a wrong, unfiltered sidebar. The Users
create/invite endpoints refuse that combination.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role

#: Role slugs on the teacher tier (see SCHOOL_PERMISSION_PRESETS in models/role.py).
TEACHING_ROLE_SLUGS = frozenset({
    "teacher", "instructor", "head_teacher", "academic_coordinator",
    "head_of_department_secondary", "head_of_early_years", "homeroom_coordinator",
    "exam_subject_head", "spa_officer", "spa_manager",
})


async def require_sections_for_teachers(
    db: AsyncSession, org_id: str, role_ids: list[str], section_ids: list[str],
) -> bool:
    """True when a teaching role is among `role_ids`; 422 if so and no section given."""
    if not role_ids:
        return False
    slugs = {s.lower() for s in (await db.execute(
        select(Role.slug).where(Role.id.in_(role_ids), Role.org_id == org_id)
    )).scalars().all()}
    teaching = bool(slugs & TEACHING_ROLE_SLUGS)
    if teaching and not [s for s in section_ids if s]:
        raise HTTPException(
            status_code=422,
            detail="section_ids: choose at least one section (Early Years, Primary or "
                   "Secondary) — it is required for a teacher.",
        )
    return teaching
