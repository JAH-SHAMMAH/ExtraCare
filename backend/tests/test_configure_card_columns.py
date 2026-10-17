import uuid
import pytest
from sqlalchemy import select
from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, Cumulative, CumulativeComponent, SchoolSection,
)
from app.models.modules.school import SchoolClass
from app.services.session_scope import load_term_setup
from scripts.configure_card_columns import plan_and_apply
from tests.conftest import ensure_session

pytestmark = pytest.mark.asyncio


async def _world(db, org):
    sess = await ensure_session(db, org)
    prim = SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Primary", curriculum="nigerian", position=1)
    sec = SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Secondary", curriculum="nigerian", position=2)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    db.add_all([prim, sec, term, sub,
                SchoolClass(id=str(uuid.uuid4()), name="Year 5 Diamond", level="Year 5", section_id=prim.id, org_id=org.id),
                SchoolClass(id=str(uuid.uuid4()), name="Year 10 Amethyst", level="Year 10", section_id=sec.id, org_id=org.id)])
    await db.commit()
    return sess, term


async def test_dry_run_changes_nothing_then_write_gives_each_level_its_own_columns(db, org):
    sess, term = await _world(db, org)
    r = await plan_and_apply(db, org.id, write=False)
    assert len(r["added"]) == (4 + 1) + (3 + 1)
    assert (await db.execute(select(Assessment))).scalars().all() == []
    await plan_and_apply(db, org.id, write=True)
    await db.commit()

    junior = await load_term_setup(db, org.id, sess.id, term.id, level="Year 5")
    assert [a.name for a in sorted(junior.assessments.values(), key=lambda a: a.position)] == ["CA 1", "PRJ", "C.E", "EXAM"]
    assert [int(a.max_score) for a in sorted(junior.assessments.values(), key=lambda a: a.position)] == [20, 10, 10, 60]
    senior = await load_term_setup(db, org.id, sess.id, term.id, level="Year 10")
    assert [a.name for a in sorted(senior.assessments.values(), key=lambda a: a.position)] == ["CA 1", "CA 2", "EXAM"]
    assert [c.name for c in senior.cumulatives] == ["TOTAL"]
    comps = (await db.execute(select(CumulativeComponent))).scalars().all()
    assert len(comps) == 4 + 3


async def test_idempotent_and_never_touches_existing_columns(db, org):
    sess, term = await _world(db, org)
    sub = (await db.execute(select(AcademicSubTerm))).scalars().first()
    old = Assessment(id=str(uuid.uuid4()), name="CBT", max_score=20, session_id=sess.id, term_id=term.id,
                     sub_term_id=sub.id, org_id=org.id)
    db.add(old)
    await db.commit()
    await plan_and_apply(db, org.id, write=True)
    await db.commit()
    again = await plan_and_apply(db, org.id, write=True)
    assert again["added"] == [] and again["existing"] > 0
    assert again["unscoped_left"] == ["CBT"]                     # reported, not removed
    assert (await db.execute(select(Assessment).where(Assessment.name == "CBT"))).scalars().one().year_group is None
