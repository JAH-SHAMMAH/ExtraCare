"""Test helper: a real AcademicTerm.

`ReportApproval.term_id` is a FK since migration 131 — it was free text, and that
free text is what silenced every parent's report card when the approvals said
'Term 1' while the school's terms were Autumn/Spring/Summer. So a test that opens
a report workflow needs an actual term row, not a string.

Get-or-create by name, so a fixture can call it more than once without tripping a
duplicate.
"""
from __future__ import annotations

import uuid


async def a_term(db, org, name: str = "Autumn", position: int = 1):
    """The org's AcademicTerm called `name`, created if absent.

    `org` may be an Organization or a bare org_id, because several fixtures only
    have the id to hand (via `cls.org_id`).
    """
    from sqlalchemy import select

    from app.models.modules.platform import AcademicTerm

    org_id = getattr(org, "id", org)
    existing = (await db.execute(select(AcademicTerm).where(
        AcademicTerm.org_id == org_id, AcademicTerm.name == name))).scalars().first()
    if existing:
        return existing
    t = AcademicTerm(id=str(uuid.uuid4()), name=name, position=position, org_id=org_id)
    db.add(t)
    await db.commit()
    return t
