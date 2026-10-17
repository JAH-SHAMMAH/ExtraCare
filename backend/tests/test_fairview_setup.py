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


async def test_boot_setup_runs_once_then_leaves_admin_edits_alone(db, org):
    from app.services.fairview_setup import auto_setup_on_boot

    class F:                       # reuse the test session as the factory
        def __call__(self): return self
        async def __aenter__(self): return db
        async def __aexit__(self, *a): return False

    stu, subj, old = await _world(db, org)
    await auto_setup_on_boot(F())
    ex = (await db.execute(select(Assessment).where(Assessment.name == "EXAM", Assessment.year_group == "YEAR 10"))).scalars().all()
    assert len(ex) == 1
    await db.delete(ex[0]); await db.commit()
    await auto_setup_on_boot(F())                                   # second boot: nothing re-added
    assert (await db.execute(select(Assessment).where(Assessment.name == "EXAM", Assessment.year_group == "YEAR 10"))).scalars().all() == []


async def test_broadsheet_names_the_cards_template(db, org):
    from app.routers.modules.platform import _report_key_for_section
    stu, subj, old = await _world(db, org)
    cls = (await db.execute(select(SchoolClass))).scalars().first()
    assert await _report_key_for_section(db, org.id, cls.section_id) == "secondary-report"


async def test_each_level_gets_its_own_letterhead_once(db, org):
    from app.models.modules.platform import ReportBranding
    from app.services.fairview_setup import ensure_letterheads
    await _world(db, org)
    first = await ensure_letterheads(db, org.id)
    await db.commit()
    assert set(first) == {"secondary-report", "junior-report"}
    names = {r.school_name_alias for r in (await db.execute(select(ReportBranding))).scalars().all()}
    assert names == {"FAIRVIEW SECONDARY SCHOOL", "FAIRVIEW SCHOOL (PRE-SCHOOL and PRIMARY)"}
    assert await ensure_letterheads(db, org.id) == []          # idempotent


async def test_card_carries_heading_teacher_session(db, org):
    from app.routers.modules.platform import report_card
    from tests.test_not_configured_sub_term import _world as nworld
    w = await nworld(db, org)
    card = await report_card(student_id=w.pupil.id, term_id=w.term.id, sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert card.heading.endswith(" SESSION") and card.heading.startswith(w.term.name.upper() + " REPORT")
    assert card.first_name and card.session_name
