"""`report-config/bootstrap` must refuse to run on an already-configured school.

WHAT IT WOULD DO OTHERWISE. The endpoint identifies "the grading scale" BY NAME
("Grading Scale (A–F)"). A school whose scale is named anything else — Fairview's
is "Nigerian Secondary (A*-F)" — is not recognised, so it creates a SECOND numeric
scale carrying the old 5-band 70/60/50/45/40, with `purpose` defaulting to 'grade'
and `show_in_table` to True.

Both resolvers (services/grading.load_grade_bands and report_card's own picker)
select numeric + purpose='grade' ordered ONLY by show_in_table, then `.first()`.
Two rows tied on show_in_table resolve arbitrarily, so every letter on every report
card could move to the wrong scale — 1,799 marks at Fairview.

THE FLAG THE GUARD DOES *NOT* USE. Fairview's real nine-band scale is
`is_provisional=True` (the school never cleared the flag), so a
"refuse if a non-provisional scale exists" guard would not fire on the one database
it needs to protect. The guard keys on a numeric grade scale EXISTING.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.platform import GradingBand, GradingScale
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import bootstrap_report_config
from tests.conftest import ensure_section

pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    r = Role(id=str(uuid.uuid4()), name="admin", slug="super_user",
             permissions=["*"], org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com",
             full_name="Officer", status=UserStatus.ACTIVE, org_id=org.id)
    db.add(r)
    u.roles = [r]
    db.add(u)
    await db.commit()
    return u


async def _fairview_scale(db, org, *, provisional: bool = True) -> GradingScale:
    """Fairview's real scale: nine bands, named nothing the bootstrap looks for,
    and flagged provisional."""
    sc = GradingScale(id=str(uuid.uuid4()), name="Nigerian Secondary (A*-F)",
                      scale_type="numeric", purpose="grade", show_in_table=True,
                      is_provisional=provisional, org_id=org.id)
    db.add(sc)
    await db.flush()
    for i, (g, lo, hi) in enumerate([
        ("A*", 95, 100), ("A", 90, 94), ("B+", 85, 89), ("B", 80, 84), ("C", 70, 79),
        ("D", 60, 69), ("E", 50, 59), ("P", 40, 49), ("F", 0, 39),
    ]):
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade=g,
                           min_score=Decimal(lo), max_score=Decimal(hi),
                           position=i, org_id=org.id))
    await db.commit()
    return sc


async def _numeric_grade_scales(db, org):
    return (await db.execute(select(GradingScale).where(
        GradingScale.org_id == org.id, GradingScale.scale_type == "numeric",
        GradingScale.purpose == "grade"))).scalars().all()


async def test_refuses_when_a_grade_scale_already_exists(db, org):
    admin = await _admin(db, org)
    await _fairview_scale(db, org)

    with pytest.raises(HTTPException) as ei:
        await bootstrap_report_config(db=db, current_user=admin)
    assert ei.value.status_code == 409
    assert "Nigerian Secondary (A*-F)" in ei.value.detail, "names the scale it found"
    assert "arbitrarily" in ei.value.detail, "says WHY, not just no"


async def test_refuses_even_though_the_scale_is_flagged_PROVISIONAL(db, org):
    """The heart of it. Fairview's live scale is provisional, so a guard keyed on
    `is_provisional` would wave this through on the exact database at risk."""
    admin = await _admin(db, org)
    sc = await _fairview_scale(db, org, provisional=True)
    assert sc.is_provisional is True

    with pytest.raises(HTTPException) as ei:
        await bootstrap_report_config(db=db, current_user=admin)
    assert ei.value.status_code == 409


async def test_the_second_scale_is_never_created(db, org):
    """The consequence the guard exists to prevent, asserted directly."""
    admin = await _admin(db, org)
    await _fairview_scale(db, org)
    assert len(await _numeric_grade_scales(db, org)) == 1

    with pytest.raises(HTTPException):
        await bootstrap_report_config(db=db, current_user=admin)

    scales = await _numeric_grade_scales(db, org)
    assert len(scales) == 1, "still exactly one — no competing scale was written"
    assert scales[0].name == "Nigerian Secondary (A*-F)"
    bands = (await db.execute(select(GradingBand).where(
        GradingBand.scale_id == scales[0].id))).scalars().all()
    assert len(bands) == 9, "and its nine bands are untouched"


async def test_no_collateral_when_it_refuses(db, org):
    """It also stamps carries_cambridge across every subject x Primary/Secondary.
    A refusal must leave none of that behind either."""
    from app.models.modules.platform import ReportSubjectAssessment, ReportTemplate
    from app.models.modules.school import Subject

    admin = await _admin(db, org)
    await _fairview_scale(db, org)
    _sec = await ensure_section(db, org)
    db.add(Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=_sec.id, org_id=org.id))
    await db.commit()

    with pytest.raises(HTTPException):
        await bootstrap_report_config(db=db, current_user=admin)

    assert (await db.execute(select(ReportSubjectAssessment).where(
        ReportSubjectAssessment.org_id == org.id))).scalars().all() == []
    assert (await db.execute(select(ReportTemplate).where(
        ReportTemplate.org_id == org.id))).scalars().all() == []


async def test_a_FRESH_school_can_still_use_it(db, org):
    """The guard must not make the tool useless — it is a first-run setup helper,
    and on an org with no grade scale it should still do its job."""
    admin = await _admin(db, org)
    assert await _numeric_grade_scales(db, org) == []

    out = await bootstrap_report_config(db=db, current_user=admin)

    assert out, "templates were created"
    modes = {t.assessment_mode for t in out}
    assert "descriptive" in modes, "Early Years gets the descriptive template"
    scales = await _numeric_grade_scales(db, org)
    assert len(scales) == 1, "exactly one grade scale on a fresh school"


async def test_a_descriptor_scale_does_not_trip_the_guard(db, org):
    """EYFS descriptors is purpose='grade' but scale_type='descriptor', and the
    numeric resolvers filter it out — so its presence must not block a fresh setup."""
    admin = await _admin(db, org)
    sc = GradingScale(id=str(uuid.uuid4()), name="EYFS descriptors",
                      scale_type="descriptor", purpose="grade", is_provisional=False,
                      org_id=org.id)
    db.add(sc)
    await db.commit()

    out = await bootstrap_report_config(db=db, current_user=admin)
    assert out, "a descriptor scale is not a numeric grade scale"


async def test_it_may_still_re_run_over_its_OWN_scale(db, org):
    """The refinement. The guard refuses a FOREIGN scale, not any scale.

    Re-running is documented self-healing — a second run replaces an earlier
    provisional seed with the confirmed constants — so blocking it would have
    removed a capability rather than a hazard. The hazard is specifically a scale
    this endpoint did not create and therefore does not recognise by name.
    """
    from app.routers.modules.platform import _BOOTSTRAP_GRADE_SCALE

    admin = await _admin(db, org)
    first = await bootstrap_report_config(db=db, current_user=admin)
    assert len(first) == 3

    scales = await _numeric_grade_scales(db, org)
    assert len(scales) == 1 and scales[0].name == _BOOTSTRAP_GRADE_SCALE

    second = await bootstrap_report_config(db=db, current_user=admin)
    assert len(second) == 3, "its own output does not block it"
    assert len(await _numeric_grade_scales(db, org)) == 1, "and still no duplicate"


async def test_a_foreign_scale_blocks_even_if_its_own_is_also_present(db, org):
    """A school that ran the bootstrap AND has its own scale is the ambiguous case
    the resolvers cannot settle — so it must refuse, not pick one."""
    admin = await _admin(db, org)
    await bootstrap_report_config(db=db, current_user=admin)
    await _fairview_scale(db, org)          # a second, foreign grade scale
    assert len(await _numeric_grade_scales(db, org)) == 2

    with pytest.raises(HTTPException) as ei:
        await bootstrap_report_config(db=db, current_user=admin)
    assert ei.value.status_code == 409
    assert "Nigerian Secondary (A*-F)" in ei.value.detail
