"""Secondary Report parity S-4b: Broadsheet — full pipeline (scores -> cumulatives
-> subject totals -> grade + position)."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.school import Subject, SchoolClass, Student
from app.models.modules.platform import AcademicTerm, AcademicSubTerm, GradingScale, GradingBand
from app.routers.modules.platform import (
    bootstrap_assessments, bootstrap_cumulatives, list_assessments,
    save_report_entry, report_broadsheet,
)
from app.schemas.platform import ReportEntrySave, ScoreItem


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Exam Officer",
             status=UserStatus.ACTIVE, org_id=org.id)
    _r = Role(id=str(uuid.uuid4()), name="admin", slug="super_user", permissions=["*"], org_id=org.id, is_system=False)
    db.add(_r)
    u.roles = [_r]
    db.add(u)
    await db.commit()
    return u


async def _grade_scale(db, org):
    sc = GradingScale(id=str(uuid.uuid4()), name="GRADING SCALE", scale_type="numeric",
                      is_provisional=False, purpose="grade", show_in_table=True, org_id=org.id)
    db.add(sc)
    await db.flush()
    # Educare 9-band scale (subset that matters here).
    for grade, lo, hi in [("A*", 95, 100), ("A", 90, 94), ("B+", 85, 89), ("B", 80, 84),
                          ("C", 70, 79), ("D", 60, 69), ("E", 50, 59), ("P", 40, 49), ("F", 0, 39)]:
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade=grade,
                           min_score=Decimal(lo), max_score=Decimal(hi), org_id=org.id))
    await db.commit()
    return sc


async def test_broadsheet_full_pipeline(db, org):
    admin = await _admin(db, org)
    autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    eng = Subject(id=str(uuid.uuid4()), name="English", org_id=org.id)
    s1 = Student(id=str(uuid.uuid4()), student_id="FS/1", first_name="Ada", last_name="Obi", class_id=cls.id, org_id=org.id)
    s2 = Student(id=str(uuid.uuid4()), student_id="FS/2", first_name="Ben", last_name="Ede", class_id=cls.id, org_id=org.id)
    db.add_all([autumn, half, full, cls, maths, eng, s1, s2])
    await db.commit()
    await _grade_scale(db, org)

    await bootstrap_assessments(db=db, current_user=admin)
    await bootstrap_cumulatives(db=db, current_user=admin)
    asmts = {a.name: a for a in await list_assessments(term_id=autumn.id, db=db, current_user=admin)}

    # Ada scores a perfect 100 in Maths (CBT20+THY20 -> CA1 20; PRJ10+PBT10+EXAM60 -> TOTAL 100).
    def full_marks(student_id, subject_id):
        return ReportEntrySave(subject_id=subject_id, items=[
            ScoreItem(student_id=student_id, assessment_id=asmts["CBT"].id, score=Decimal("20")),
            ScoreItem(student_id=student_id, assessment_id=asmts["THEORY"].id, score=Decimal("20")),
            ScoreItem(student_id=student_id, assessment_id=asmts["PRJ"].id, score=Decimal("10")),
            ScoreItem(student_id=student_id, assessment_id=asmts["PBT"].id, score=Decimal("10")),
            ScoreItem(student_id=student_id, assessment_id=asmts["EXAM"].id, score=Decimal("60")),
        ])
    await save_report_entry(payload=full_marks(s1.id, maths.id), db=db, current_user=admin)
    await save_report_entry(payload=full_marks(s1.id, eng.id), db=db, current_user=admin)
    # Ben: CBT18 THY16 (CA1 = 34/40*20 = 17), PRJ8 PBT9 EXAM50 -> TOTAL 84, in Maths only.
    await save_report_entry(payload=ReportEntrySave(subject_id=maths.id, items=[
        ScoreItem(student_id=s2.id, assessment_id=asmts["CBT"].id, score=Decimal("18")),
        ScoreItem(student_id=s2.id, assessment_id=asmts["THEORY"].id, score=Decimal("16")),
        ScoreItem(student_id=s2.id, assessment_id=asmts["PRJ"].id, score=Decimal("8")),
        ScoreItem(student_id=s2.id, assessment_id=asmts["PBT"].id, score=Decimal("9")),
        ScoreItem(student_id=s2.id, assessment_id=asmts["EXAM"].id, score=Decimal("50")),
    ]), db=db, current_user=admin)

    bs = await report_broadsheet(class_id=cls.id, term_id=autumn.id, sub_term_id=full.id, db=db, current_user=admin)
    assert bs.display_cumulative == "TOTAL"
    assert {s.name for s in bs.subjects} == {"Mathematics", "English"}

    by_name = {r.student_name: r for r in bs.rows}
    ada, ben = by_name["Ada Obi"], by_name["Ben Ede"]
    # Ada: Maths + English both 100 -> total 200, avg 100, A*, 1st.
    assert ada.subjects[maths.id].value == Decimal("100") and ada.subjects[maths.id].grade == "A*"
    assert ada.total == Decimal("200") and ada.average == Decimal("100") and ada.grade == "A*" and ada.position == 1
    # Ben: Maths 84 (B), English not entered (None). total 84, avg 84, position 2.
    assert ben.subjects[maths.id].value == Decimal("84") and ben.subjects[maths.id].grade == "B"
    assert ben.subjects[eng.id].value is None
    assert ben.total == Decimal("84") and ben.average == Decimal("84") and ben.position == 2

    # 9-band legend rides along.
    assert any(b.grade == "A*" for b in bs.bands)
