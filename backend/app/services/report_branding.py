"""Which report_branding row applies: the section's own, else the school default."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modules.platform import ReportBranding


async def get_branding_row(db: AsyncSession, org_id: str, section_id: str | None = None):
    """(row, inherited). `inherited` is True when a section was asked for but only
    the school-wide default exists. row is None when neither exists."""
    if section_id:
        row = (await db.execute(select(ReportBranding).where(
            ReportBranding.org_id == org_id, ReportBranding.section_id == section_id,
        ))).scalars().first()
        if row:
            return row, False
    row = (await db.execute(select(ReportBranding).where(
        ReportBranding.org_id == org_id, ReportBranding.section_id.is_(None),
    ))).scalars().first()
    return row, bool(section_id and row)
