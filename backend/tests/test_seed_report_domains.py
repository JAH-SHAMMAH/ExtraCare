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
    n = len(SPECS["secondary-report"]["groups"][0]["items"])
    r = await seed(db, org.id, "secondary-report", write=False)
    assert len(r["added"]) == n and r["scales_created"] == 1
    assert (await db.execute(select(AssessmentDomain))).scalars().all() == []
    await seed(db, org.id, "secondary-report", write=True)
    await db.commit()
    again = await seed(db, org.id, "secondary-report", write=True)
    assert again["added"] == [] and len(again["existing"]) == n and again["scales_created"] == 0
    assert len((await db.execute(select(AssessmentDomain))).scalars().all()) == n


async def test_junior_has_both_blocks_and_shared_key(db, org):
    await _sections(db, org)
    await seed(db, org.id, "junior-report", write=True)
    await db.commit()
    rows = (await db.execute(select(AssessmentDomain))).scalars().all()
    kinds = {k: [d.name for d in rows if d.domain_type == k] for k in ("affective", "psychomotor")}
    assert len(kinds["affective"]) == 15 and len(kinds["psychomotor"]) == 8
    assert len({d.rating_scale_id for d in rows}) == 1        # one printed KEYS box


async def test_nursery_eighteen_goals_in_eight_areas(db, org):
    db.add_all([SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Early Years", curriculum="eyfs", position=0),
                SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Primary", curriculum="nigerian", position=1),
                SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Secondary", curriculum="nigerian", position=2)])
    await db.commit()
    dry = await seed(db, org.id, "nursery-report", write=False)
    assert len(dry["added"]) == 8 + 18
    await seed(db, org.id, "nursery-report", write=True)
    await db.commit()
    rows = (await db.execute(select(AssessmentDomain))).scalars().all()
    areas = [d for d in rows if d.domain_type == "eyfs_area"]
    goals = [d for d in rows if d.domain_type == "eyfs_goal"]
    assert len(areas) == 8 and len(goals) == 18
    assert all(g.parent_domain_id in {a.id for a in areas} for g in goals)
    again = await seed(db, org.id, "nursery-report", write=True)
    assert again["added"] == []                                  # idempotent


async def test_unknown_key_is_refused(db, org):
    await _sections(db, org)
    with pytest.raises(SystemExit):
        await seed(db, org.id, "primary-report", write=True)
