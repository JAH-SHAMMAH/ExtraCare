import uuid
import pytest
from sqlalchemy import select
from app.models.modules.platform import AssessmentDomain, SchoolSection
from scripts.seed_report_domains import SPECS, seed

pytestmark = pytest.mark.asyncio


async def _sections(db, org):
    db.add_all([SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Primary", curriculum="nigerian", position=1),
                SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Secondary", curriculum="nigerian", position=2)])
    await db.commit()


async def test_dry_run_writes_nothing_then_write_is_idempotent(db, org):
    await _sections(db, org)
    n = len(SPECS["secondary-report"]["items"])
    r = await seed(db, org.id, "secondary-report", write=False)
    assert len(r["added"]) == n and r["scale_created"]
    assert (await db.execute(select(AssessmentDomain))).scalars().all() == []
    await seed(db, org.id, "secondary-report", write=True)
    await db.commit()
    again = await seed(db, org.id, "secondary-report", write=True)
    assert again["added"] == [] and len(again["existing"]) == n and not again["scale_created"]
    assert len((await db.execute(select(AssessmentDomain))).scalars().all()) == n


async def test_unknown_key_is_refused(db, org):
    await _sections(db, org)
    with pytest.raises(SystemExit):
        await seed(db, org.id, "junior-report", write=True)
