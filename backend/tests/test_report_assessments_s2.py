"""Secondary Report parity S-2: Assessment Group + Assessment leaf components."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.platform import AcademicTerm, AcademicSubTerm
from app.routers.modules.platform import (
    create_assessment_group, list_assessment_groups, delete_assessment_group,
    create_assessment, list_assessments, update_assessment, delete_assessment,
    bootstrap_assessments,
)
from app.schemas.platform import (
    AssessmentGroupCreate, AssessmentCreate, AssessmentUpdate,
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
    spring = AcademicTerm(id=str(uuid.uuid4()), name="Spring", position=2, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    db.add_all([autumn, spring, half, full])
    await db.commit()
    return autumn, spring, half, full


async def test_assessment_groups(db, org):
    admin = await _admin(db, org)
    g = await create_assessment_group(payload=AssessmentGroupCreate(name="Continuous Assessment"), db=db, current_user=admin)
    assert g.name == "Continuous Assessment"
    with pytest.raises(HTTPException) as ei:
        await create_assessment_group(payload=AssessmentGroupCreate(name="continuous assessment"), db=db, current_user=admin)
    assert ei.value.status_code == 409
    assert len(await list_assessment_groups(db=db, current_user=admin)) == 1
    await delete_assessment_group(g.id, db=db, current_user=admin)
    assert len(await list_assessment_groups(db=db, current_user=admin)) == 0


async def test_assessment_crud_and_filter(db, org):
    admin = await _admin(db, org)
    autumn, spring, half, full = await _terms(db, org)

    a = await create_assessment(payload=AssessmentCreate(
        name="EXAM", code="EXM", max_score=Decimal("60"), term_id=autumn.id, sub_term_id=full.id, decimal_places=0),
        db=db, current_user=admin)
    assert a.term_name == "Autumn" and a.sub_term_name == "Full-Term" and a.max_score == Decimal("60")

    # Bad term / sub-term rejected.
    with pytest.raises(HTTPException) as ei:
        await create_assessment(payload=AssessmentCreate(name="X", term_id="nope", sub_term_id=full.id), db=db, current_user=admin)
    assert ei.value.status_code == 422

    await create_assessment(payload=AssessmentCreate(name="CBT", max_score=Decimal("20"), term_id=spring.id, sub_term_id=half.id), db=db, current_user=admin)
    # Term filter.
    assert len(await list_assessments(term_id=autumn.id, db=db, current_user=admin)) == 1
    assert len(await list_assessments(term_id=spring.id, db=db, current_user=admin)) == 1
    assert len(await list_assessments(term_id=None, db=db, current_user=admin)) == 2

    a2 = await update_assessment(a.id, AssessmentUpdate(max_score=Decimal("50")), db=db, current_user=admin)
    assert a2.max_score == Decimal("50")
    await delete_assessment(a.id, db=db, current_user=admin)
    assert len(await list_assessments(term_id=autumn.id, db=db, current_user=admin)) == 0


async def test_assessment_bootstrap(db, org):
    admin = await _admin(db, org)
    autumn, spring, half, full = await _terms(db, org)

    rows = await bootstrap_assessments(db=db, current_user=admin)
    # 5 components per term (CBT/THEORY half + PRJ/PBT/EXAM full) x 2 terms = 10.
    assert len(rows) == 10
    autumn_rows = await list_assessments(term_id=autumn.id, db=db, current_user=admin)
    names = {r.name for r in autumn_rows}
    assert names == {"CBT", "THEORY", "PRJ", "PBT", "EXAM"}
    exam = next(r for r in autumn_rows if r.name == "EXAM")
    assert exam.max_score == Decimal("60") and exam.sub_term_name == "Full-Term"
    cbt = next(r for r in autumn_rows if r.name == "CBT")
    assert cbt.max_score == Decimal("20") and cbt.sub_term_name == "Half-Term"

    # Idempotent — second run adds nothing.
    rows2 = await bootstrap_assessments(db=db, current_user=admin)
    assert len(rows2) == 10
