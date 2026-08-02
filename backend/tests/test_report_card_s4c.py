"""Secondary Report parity S-4c: printable report card (per-subject breakdown)."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.user import User, UserStatus
from app.models.modules.school import Subject, SchoolClass, Student
from app.models.modules.platform import AcademicTerm, AcademicSubTerm, GradingScale, GradingBand
from app.routers.modules.platform import (
    bootstrap_assessments, bootstrap_cumulatives, list_assessments,
    save_report_entry, report_card,
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


async def _grade_scale(db, org):
    sc = GradingScale(id=str(uuid.uuid4()), name="GRADING SCALE", scale_type="numeric",
                      is_provisional=False, purpose="grade", show_in_table=True, org_id=org.id)
    db.add(sc)
    await db.flush()
    for grade, lo, hi in [("A*", 95, 100), ("A", 90, 94), ("B+", 85, 89), ("B", 80, 84),
                          ("C", 70, 79), ("D", 60, 69), ("E", 50, 59), ("P", 40, 49), ("F", 0, 39)]:
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade=grade, remark=grade + "-remark",
                           min_score=Decimal(lo), max_score=Decimal(hi), org_id=org.id))
    await db.commit()


async def test_report_card_full_term(db, org):
    admin = await _admin(db, org)
    autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    s1 = Student(id=str(uuid.uuid4()), student_id="FSS/22/047", first_name="Chi", last_name="Okeke", class_id=cls.id, org_id=org.id)
    s2 = Student(id=str(uuid.uuid4()), student_id="FSS/22/048", first_name="Ben", last_name="Ede", class_id=cls.id, org_id=org.id)
    db.add_all([autumn, half, full, cls, maths, s1, s2])
    await db.commit()
    await _grade_scale(db, org)
    await bootstrap_assessments(db=db, current_user=admin)
    await bootstrap_cumulatives(db=db, current_user=admin)
    A = {a.name: a for a in await list_assessments(term_id=autumn.id, db=db, current_user=admin)}

    async def enter(student, subj, cbt, thy, prj, pbt, exam):
        await save_report_entry(payload=ReportEntrySave(subject_id=subj, items=[
            ScoreItem(student_id=student, assessment_id=A["CBT"].id, score=Decimal(cbt)),
            ScoreItem(student_id=student, assessment_id=A["THEORY"].id, score=Decimal(thy)),
            ScoreItem(student_id=student, assessment_id=A["PRJ"].id, score=Decimal(prj)),
            ScoreItem(student_id=student, assessment_id=A["PBT"].id, score=Decimal(pbt)),
            ScoreItem(student_id=student, assessment_id=A["EXAM"].id, score=Decimal(exam)),
        ]), db=db, current_user=admin)

    await enter(s1.id, maths.id, 18, 16, 8, 9, 50)     # CA1 17 + 8+9+50 = 84
    await enter(s2.id, maths.id, 20, 20, 10, 10, 60)   # 100 (ranks 1st)

    card = await report_card(student_id=s1.id, term_id=autumn.id, sub_term_id=full.id, db=db, current_user=admin)
    assert card.student_name == "Chi Okeke" and card.admission_no == "FSS/22/047"
    assert "AUTUMN" in card.report_title and "FULL-TERM" in card.report_title
    # Full-term columns include CA 1, PRJ, PBT, EXAM, TOTAL.
    col_names = {c.name for c in card.columns}
    assert {"CA 1", "PRJ", "PBT", "EXAM", "TOTAL"} <= col_names

    row = next(r for r in card.subjects if r.subject_name == "Mathematics")
    total_col = next(c for c in card.columns if c.name == "TOTAL")
    ca1_col = next(c for c in card.columns if c.name == "CA 1")
    assert row.values[total_col.key] == Decimal("84") and row.values[ca1_col.key] == Decimal("17")
    assert row.grade == "B" and row.remark == "B-remark"
    assert row.subject_arm_average == Decimal("92.00")     # (84 + 100) / 2

    # This pupil is 2nd of 2; totals/average reflect the single subject.
    assert card.total == Decimal("84") and card.average == Decimal("84") and card.grade == "B"
    assert card.position == 2 and card.class_size == 2
    assert any(b.grade == "A*" for b in card.bands)
