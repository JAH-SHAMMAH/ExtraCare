"""Secondary Report parity S-3: Cumulative curated engine (config + bootstrap)."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.platform import AcademicTerm, AcademicSubTerm
from app.routers.modules.platform import (
    create_assessment, bootstrap_assessments,
    create_cumulative, list_cumulatives, update_cumulative,
    replace_cumulative_components, delete_cumulative, bootstrap_cumulatives,
)
from app.schemas.platform import (
    AssessmentCreate, CumulativeCreate, CumulativeUpdate, CumulComponentIn,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Exam Officer",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _terms(db, org):
    autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    db.add_all([autumn, half, full])
    await db.commit()
    return autumn, half, full


async def test_cumulative_config(db, org):
    admin = await _admin(db, org)
    autumn, half, full = await _terms(db, org)
    cbt = await create_assessment(payload=AssessmentCreate(name="CBT", max_score=Decimal("20"), term_id=autumn.id, sub_term_id=half.id), db=db, current_user=admin)
    thy = await create_assessment(payload=AssessmentCreate(name="THEORY", max_score=Decimal("20"), term_id=autumn.id, sub_term_id=half.id), db=db, current_user=admin)

    htt = await create_cumulative(payload=CumulativeCreate(
        name="HALF TERM TOTAL", term_id=autumn.id, sub_term_id=half.id, cumul_type="score",
        components=[CumulComponentIn(ref_type="assessment", ref_id=cbt.id), CumulComponentIn(ref_type="assessment", ref_id=thy.id)]),
        db=db, current_user=admin)
    assert len(htt.components) == 2 and {c.label for c in htt.components} == {"CBT", "THEORY"}

    # Nested cumulative reference.
    ca1 = await create_cumulative(payload=CumulativeCreate(
        name="CA 1", term_id=autumn.id, sub_term_id=half.id, cumul_type="custom_percentage", max_percent=Decimal("20"),
        components=[CumulComponentIn(ref_type="cumulative", ref_id=htt.id)]),
        db=db, current_user=admin)
    assert ca1.cumul_type == "custom_percentage" and ca1.max_percent == Decimal("20")
    assert ca1.components[0].ref_type == "cumulative" and ca1.components[0].label == "HALF TERM TOTAL"

    # Bad cumul_type + unknown component rejected.
    with pytest.raises(HTTPException) as ei:
        await create_cumulative(payload=CumulativeCreate(name="X", term_id=autumn.id, sub_term_id=half.id, cumul_type="magic"), db=db, current_user=admin)
    assert ei.value.status_code == 422
    with pytest.raises(HTTPException) as ei:
        await create_cumulative(payload=CumulativeCreate(name="Y", term_id=autumn.id, sub_term_id=half.id,
                                components=[CumulComponentIn(ref_type="assessment", ref_id="nope")]), db=db, current_user=admin)
    assert ei.value.status_code == 422

    # Replace components + update.
    htt2 = await replace_cumulative_components(htt.id, [CumulComponentIn(ref_type="assessment", ref_id=cbt.id)], db=db, current_user=admin)
    assert len(htt2.components) == 1
    upd = await update_cumulative(htt.id, CumulativeUpdate(decimal_places=2), db=db, current_user=admin)
    assert upd.decimal_places == 2

    assert len(await list_cumulatives(term_id=autumn.id, db=db, current_user=admin)) == 2
    await delete_cumulative(ca1.id, db=db, current_user=admin)
    assert len(await list_cumulatives(term_id=None, db=db, current_user=admin)) == 1


async def test_cumulative_bootstrap(db, org):
    admin = await _admin(db, org)
    autumn, half, full = await _terms(db, org)
    await bootstrap_assessments(db=db, current_user=admin)   # seeds CBT/THEORY/PRJ/PBT/EXAM

    rows = await bootstrap_cumulatives(db=db, current_user=admin)
    names = {c.name for c in rows}
    assert {"HALF TERM TOTAL", "%", "CA 1", "TOTAL"} <= names

    total = next(c for c in rows if c.name == "TOTAL")
    labels = {(c.ref_type, c.label) for c in total.components}
    assert ("cumulative", "CA 1") in labels
    assert ("assessment", "EXAM") in labels and ("assessment", "PRJ") in labels

    ca1 = next(c for c in rows if c.name == "CA 1")
    assert ca1.cumul_type == "custom_percentage" and ca1.max_percent == Decimal("20")
    assert ca1.components[0].label == "HALF TERM TOTAL"

    # Idempotent.
    rows2 = await bootstrap_cumulatives(db=db, current_user=admin)
    assert len([c for c in rows2 if c.name == "TOTAL"]) == 1
