"""Secondary Report parity S-5: Result Insight (gender / subject / class averages)."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.user import User, UserStatus
from app.models.modules.school import Subject, SchoolClass, Student
from app.models.modules.platform import AcademicTerm, AcademicSubTerm
from app.routers.modules.platform import (
    bootstrap_assessments, bootstrap_cumulatives, list_assessments, save_report_entry, report_insight,
)
from app.schemas.platform import ReportEntrySave, ScoreItem


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Officer",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_report_insight(db, org):
    admin = await _admin(db, org)
    autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    c10 = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    boy = Student(id=str(uuid.uuid4()), student_id="B1", first_name="Ben", last_name="M", gender="Male", class_id=c10.id, org_id=org.id)
    girl = Student(id=str(uuid.uuid4()), student_id="G1", first_name="Amy", last_name="F", gender="Female", class_id=c10.id, org_id=org.id)
    db.add_all([autumn, half, full, c10, maths, boy, girl])
    await db.commit()
    await bootstrap_assessments(db=db, current_user=admin)
    await bootstrap_cumulatives(db=db, current_user=admin)
    A = {a.name: a for a in await list_assessments(term_id=autumn.id, db=db, current_user=admin)}

    async def enter(student, exam):   # only EXAM scored -> TOTAL = exam value
        await save_report_entry(payload=ReportEntrySave(subject_id=maths.id, items=[
            ScoreItem(student_id=student, assessment_id=A["EXAM"].id, score=Decimal(exam))]), db=db, current_user=admin)

    await enter(boy.id, 60)     # TOTAL 60 -> 60%
    await enter(girl.id, 80)    # TOTAL 80 -> 80%

    ins = await report_insight(term_id=autumn.id, sub_term_id=full.id, db=db, current_user=admin)
    assert ins.term_name == "Autumn"
    subj = next(s for s in ins.subjects if s.subject_name == "Mathematics")
    assert subj.average == Decimal("70.0")           # (60 + 80) / 2
    gen = next(g for g in ins.gender if g.subject_name == "Mathematics")
    assert gen.male == Decimal("60.0") and gen.female == Decimal("80.0")
    cls = next(c for c in ins.classes if c.class_name == "Year 10")
    assert cls.average == Decimal("70.0")

    # Empty when nothing entered for the other sub-term set (half has no scores here
    # -> display still resolves but produces no subject rows only if no scores; here
    # scores exist term-wide, so half-term display also computes) — sanity: subjects present.
    assert len(ins.subjects) == 1
