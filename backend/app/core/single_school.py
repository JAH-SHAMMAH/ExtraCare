"""
Single-school org resolution
=============================
In single-school (Fairview) mode there is exactly one organisation and users
never choose it — the server resolves it for them. This module is the one
place that answers "which org is *the* school?", so auth, seeds, and any
boundary code stay consistent.

Resolution order:
  1. The organisation whose slug == settings.SCHOOL_ORG_SLUG (the seeded one).
  2. Fallback: if the database holds exactly one active org, use it. This makes
     fresh/dev environments forgiving when the slug hasn't been set yet.

Returns None only when neither holds (e.g. empty DB before seeding), letting
callers raise a clear, configuration-shaped error instead of a vague 404.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.organization import Organization

settings = get_settings()


async def get_school_org(db: AsyncSession) -> Organization | None:
    """Resolve the canonical single-school organisation, or None if unset."""
    org = (
        await db.execute(
            select(Organization).where(
                Organization.slug == settings.SCHOOL_ORG_SLUG,
                Organization.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if org is not None:
        return org

    # Forgiving fallback: a single-org database is unambiguously "the school".
    rows = (
        await db.execute(
            select(Organization)
            .where(
                Organization.is_active == True,  # noqa: E712
                Organization.is_deleted == False,  # noqa: E712
            )
            .limit(2)
        )
    ).scalars().all()
    if len(rows) == 1:
        return rows[0]
    return None
