"""Phase D: a section can carry its own report letterhead; the school default is the fallback."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.modules.platform import ReportBranding, SchoolSection
from app.models.user import User, UserStatus
from app.routers.modules.platform import get_report_branding, update_report_branding
from app.schemas.platform import BrandingUpdate
from app.services.report_branding import get_branding_row
from app.services.result_analysis import resolve_thresholds

pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Registrar",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _section(db, org, name) -> SchoolSection:
    s = SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name=name)
    db.add(s)
    await db.commit()
    return s


async def test_section_without_row_inherits_default(db, org):
    admin = await _admin(db, org)
    sec = await _section(db, org, "Nursery")
    await update_report_branding(payload=BrandingUpdate(school_motto="Soaring High"), db=db, current_user=admin)
    got = await get_report_branding(section_id=sec.id, db=db, current_user=admin)
    assert got.school_motto == "Soaring High" and got.inherited is True


async def test_section_row_wins_and_default_untouched(db, org):
    admin = await _admin(db, org)
    sec = await _section(db, org, "Secondary")
    await update_report_branding(payload=BrandingUpdate(school_motto="Default motto"), db=db, current_user=admin)
    s = await update_report_branding(payload=BrandingUpdate(school_motto="Secondary motto"),
                                     section_id=sec.id, db=db, current_user=admin)
    assert s.section_id == sec.id and s.school_motto == "Secondary motto"
    assert (await get_report_branding(section_id=sec.id, db=db, current_user=admin)).inherited is False
    default = await get_report_branding(db=db, current_user=admin)
    assert default.school_motto == "Default motto" and default.section_id is None


async def test_second_put_updates_same_section_row(db, org):
    admin = await _admin(db, org)
    sec = await _section(db, org, "Junior")
    a = await update_report_branding(payload=BrandingUpdate(school_motto="A"), section_id=sec.id, db=db, current_user=admin)
    b = await update_report_branding(payload=BrandingUpdate(school_head_name="Mrs X"), section_id=sec.id, db=db, current_user=admin)
    assert a.id == b.id and b.school_motto == "A"


async def test_unknown_or_foreign_section_is_404(db, org):
    admin = await _admin(db, org)
    with pytest.raises(HTTPException) as ei:
        await update_report_branding(payload=BrandingUpdate(school_motto="x"),
                                     section_id=str(uuid.uuid4()), db=db, current_user=admin)
    assert ei.value.status_code == 404


async def test_database_refuses_two_defaults_and_two_rows_per_section(db, org):
    sec_id = (await _section(db, org, "Nursery")).id
    org_id = org.id
    db.add(ReportBranding(id=str(uuid.uuid4()), org_id=org_id))
    await db.commit()
    db.add(ReportBranding(id=str(uuid.uuid4()), org_id=org_id))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
    db.add(ReportBranding(id=str(uuid.uuid4()), org_id=org_id, section_id=sec_id))
    await db.commit()
    db.add(ReportBranding(id=str(uuid.uuid4()), org_id=org_id, section_id=sec_id))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_passmark_resolves_per_section_then_default(db, org):
    admin = await _admin(db, org)
    sec = await _section(db, org, "Secondary")
    other = await _section(db, org, "Nursery")
    await update_report_branding(payload=BrandingUpdate(full_term_passmark=Decimal("40"), min_average_honours=Decimal("80")),
                                 db=db, current_user=admin)
    await update_report_branding(payload=BrandingUpdate(full_term_passmark=Decimal("50"), min_average_honours=Decimal("75")),
                                 section_id=sec.id, db=db, current_user=admin)
    p, h, _ = await resolve_thresholds(db, org.id, None, sec.id)
    assert (p, h) == (Decimal("50"), Decimal("75"))
    p, h, _ = await resolve_thresholds(db, org.id, None, other.id)   # no row: default
    assert (p, h) == (Decimal("40"), Decimal("80"))
    p, h, _ = await resolve_thresholds(db, org.id, None)             # old call shape
    assert (p, h) == (Decimal("40"), Decimal("80"))


async def test_no_rows_at_all(db, org):
    row, inherited = await get_branding_row(db, org.id, str(uuid.uuid4()))
    assert row is None and inherited is False
