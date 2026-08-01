"""Secondary Report parity S-1b: Grading System (show_in_table/purpose) + branding."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.routers.modules.platform import (
    create_scale, update_scale, list_scales,
    get_report_branding, update_report_branding,
)
from app.schemas.platform import GradingScaleCreate, GradingScaleUpdate, ScaleBandCreate, BrandingUpdate


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Registrar",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_grading_scale_flags(db, org):
    admin = await _admin(db, org)
    s = await create_scale(payload=GradingScaleCreate(
        name="MOCK GRADING SCALE", scale_type="numeric", purpose="mock", show_in_table=True,
        bands=[ScaleBandCreate(grade="A", min_score=Decimal("70"), max_score=Decimal("100"), position=0)]),
        db=db, current_user=admin)
    assert s.purpose == "mock" and s.show_in_table is True and len(s.bands) == 1

    # Bad purpose rejected on create.
    with pytest.raises(HTTPException) as ei:
        await create_scale(payload=GradingScaleCreate(name="X", purpose="legendary"), db=db, current_user=admin)
    assert ei.value.status_code == 422

    s2 = await update_scale(s.id, GradingScaleUpdate(show_in_table=False, purpose="cumulative"), db=db, current_user=admin)
    assert s2.show_in_table is False and s2.purpose == "cumulative"
    # Bad purpose rejected on update.
    with pytest.raises(HTTPException) as ei:
        await update_scale(s.id, GradingScaleUpdate(purpose="nope"), db=db, current_user=admin)
    assert ei.value.status_code == 422

    scales = await list_scales(db=db, current_user=admin)
    assert any(x.purpose == "cumulative" and x.show_in_table is False for x in scales)


async def test_report_branding_upsert(db, org):
    admin = await _admin(db, org)
    # Empty before set.
    b0 = await get_report_branding(db=db, current_user=admin)
    assert b0.id is None and b0.school_motto is None

    b1 = await update_report_branding(payload=BrandingUpdate(
        school_motto="Soaring High", school_name_alias="FAIRVIEW SECONDARY SCHOOL",
        school_head_title="Principal", full_term_passmark=Decimal("45")), db=db, current_user=admin)
    assert b1.school_motto == "Soaring High" and b1.full_term_passmark == Decimal("45") and b1.id

    # Second PUT updates the SAME row (one per org).
    b2 = await update_report_branding(payload=BrandingUpdate(school_head_name="Mrs Chinyere Nzeson"), db=db, current_user=admin)
    assert b2.id == b1.id and b2.school_head_name == "Mrs Chinyere Nzeson"
    assert b2.school_motto == "Soaring High"   # earlier field preserved

    got = await get_report_branding(db=db, current_user=admin)
    assert got.id == b1.id and got.school_name_alias == "FAIRVIEW SECONDARY SCHOOL"
