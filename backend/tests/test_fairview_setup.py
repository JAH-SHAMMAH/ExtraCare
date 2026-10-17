import uuid
import pytest
from decimal import Decimal
from sqlalchemy import select
from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, SchoolSection, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.services.fairview_setup import run_setup
from app.services.legacy_marks import split_percentage
from tests.conftest import ensure_session

pytestmark = pytest.mark.asyncio


def test_split_is_exact_and_proportional():
    parts = split_percentage(Decimal("74"), {"CA 1": Decimal(20), "CA 2": Decimal(20), "EXAM": Decimal(60)}, "EXAM")
    assert parts == {"CA 1": 15, "CA 2": 15, "EXAM": 44} and sum(parts.values()) == 74
    p2 = split_percentage(Decimal("100"), {"CA 1": Decimal(20), "PRJ": Decimal(10), "C.E": Decimal(10), "EXAM": Decimal(60)}, "EXAM")
    assert sum(p2.values()) == 100 and p2["EXAM"] == 60


async def _world(db, org):
    sess = await ensure_session(db, org)
    prim = SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Primary", curriculum="nigerian", position=1)
    sec = SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Secondary", curriculum="nigerian", position=2)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    db.add_all([prim, sec, term, sub])
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10 A", level="Year 10", section_id=sec.id, org_id=org.id)
    db.add(cls)
    subj = Subject(id=str(uuid.uuid4()), name="Maths", section_id=sec.id, org_id=org.id)
    stu = Student(id=str(uuid.uuid4()), student_id="S/1", first_name="A", last_name="B", class_id=cls.id, org_id=org.id)
    old = Assessment(id=str(uuid.uuid4()), name="Old", max_score=100, session_id=sess.id, term_id=term.id,
                     sub_term_id=sub.id, org_id=org.id)
    db.add_all([subj, stu, old])
    await db.flush()
    db.add(StudentAssessmentScore(student_id=stu.id, subject_id=subj.id, assessment_id=old.id, score=74, org_id=org.id))
    await db.commit()
    return stu, subj, old


async def test_preview_changes_nothing_apply_carries_marks_and_hides_old(db, org):
    stu, subj, old = await _world(db, org)
    pre = await run_setup(db, org.id, write=False)
    assert pre["marks"]["scores_added"] == 3
    assert len((await db.execute(select(StudentAssessmentScore))).scalars().all()) == 1

    await run_setup(db, org.id, write=True)
    await db.commit()
    rows = (await db.execute(select(StudentAssessmentScore, Assessment).join(
        Assessment, Assessment.id == StudentAssessmentScore.assessment_id)
        .where(StudentAssessmentScore.student_id == stu.id))).all()
    new = {a.name: Decimal(s.score) for s, a in rows if a.year_group != "LEGACY" and a.id != old.id}
    assert sum(new.values()) == 74 and set(new) == {"CA 1", "CA 2", "EXAM"}
    oldrow = (await db.execute(select(Assessment).where(Assessment.id == old.id))).scalars().one()
    assert oldrow.year_group == "LEGACY"
    assert any(a.id == old.id and Decimal(s.score) == 74 for s, a in rows)   # old score kept

    again = await run_setup(db, org.id, write=True)                          # idempotent
    await db.commit()
    assert again["marks"]["scores_added"] == 0
