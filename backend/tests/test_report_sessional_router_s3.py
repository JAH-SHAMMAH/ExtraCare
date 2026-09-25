"""Step 3: the Sessional Score through report_card — the wiring, not the maths.

test_report_sessional_s3.py proves the arithmetic on the pure function. These
prove report_card walks every term of the session, picks each term's OWN display
cumulative, and does not let one term's assessments leak into another's columns.

That last one is the trap this feature had to avoid. Sub-terms are org-wide
(AcademicSubTerm carries no term link), so one sub_term_id is shared by all three
terms. Widening the card's assessment load to every term — the obvious way to
compute a session figure — would feed `asmt_cols`, which filters on sub_term_id
alone, and print Summer's columns on an Autumn card.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, GradingBand, GradingScale,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import (
    bootstrap_assessments, bootstrap_cumulatives, list_assessments,
    report_card, save_report_entry,
)
from app.schemas.platform import ReportEntrySave, ScoreItem

pytestmark = pytest.mark.asyncio


async def _admin(db, org):
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com",
             full_name="Officer", status=UserStatus.ACTIVE, org_id=org.id)
    r = Role(id=str(uuid.uuid4()), name="admin", slug="super_user",
             permissions=["*"], org_id=org.id, is_system=False)
    db.add(r)
    u.roles = [r]
    db.add(u)
    await db.commit()
    return u


async def _scale(db, org):
    sc = GradingScale(id=str(uuid.uuid4()), name="GRADING SCALE", scale_type="numeric",
                      is_provisional=False, purpose="grade", show_in_table=True, org_id=org.id)
    db.add(sc)
    await db.flush()
    for grade, lo, hi in [("A*", 95, 100), ("A", 90, 94), ("B+", 85, 89), ("B", 80, 84),
                          ("C", 70, 79), ("D", 60, 69), ("E", 50, 59), ("P", 40, 49),
                          ("F", 0, 39)]:
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade=grade,
                           remark=grade + "-remark", min_score=Decimal(lo),
                           max_score=Decimal(hi), org_id=org.id))
    await db.commit()


async def _session(db, org, term_names):
    """A session of `term_names`, the Half/Full sub-terms, one class, one pupil,
    one subject, plus the curated assessment + cumulative structure."""
    terms = [AcademicTerm(id=str(uuid.uuid4()), name=n, position=i + 1, org_id=org.id)
             for i, n in enumerate(term_names)]
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    pupil = Student(id=str(uuid.uuid4()), student_id="FSS/22/047", first_name="Chi",
                    last_name="Okeke", class_id=cls.id, org_id=org.id)
    db.add_all(terms + [half, full, cls, maths, pupil])
    await db.commit()
    admin = await _admin(db, org)
    await _scale(db, org)
    await bootstrap_assessments(db=db, current_user=admin)
    await bootstrap_cumulatives(db=db, current_user=admin)
    return admin, terms, full, maths, pupil


async def _enter(db, admin, pupil, subj, term, marks):
    """marks = (cbt, theory, prj, pbt, exam). TOTAL maxes to 100:
    CA 1 (20, rescaled from CBT+THEORY out of 40) + PRJ 10 + PBT 10 + EXAM 60."""
    A = {a.name: a for a in await list_assessments(term_id=term.id, db=db, current_user=admin)}
    cbt, thy, prj, pbt, exam = marks
    await save_report_entry(payload=ReportEntrySave(subject_id=subj.id, items=[
        ScoreItem(student_id=pupil.id, assessment_id=A["CBT"].id, score=Decimal(cbt)),
        ScoreItem(student_id=pupil.id, assessment_id=A["THEORY"].id, score=Decimal(thy)),
        ScoreItem(student_id=pupil.id, assessment_id=A["PRJ"].id, score=Decimal(prj)),
        ScoreItem(student_id=pupil.id, assessment_id=A["PBT"].id, score=Decimal(pbt)),
        ScoreItem(student_id=pupil.id, assessment_id=A["EXAM"].id, score=Decimal(exam)),
    ]), db=db, current_user=admin)


async def test_sessional_is_mean_of_two_marked_terms(db, org):
    admin, terms, full, maths, pupil = await _session(db, org, ["Autumn", "Spring"])
    autumn, spring = terms
    await _enter(db, admin, pupil, maths, autumn, (18, 16, 8, 9, 50))   # CA1 17 -> 84
    await _enter(db, admin, pupil, maths, spring, (10, 10, 5, 5, 44))   # CA1 10 -> 64

    card = await report_card(student_id=pupil.id, term_id=autumn.id,
                             sub_term_id=full.id, db=db, current_user=admin)

    assert card.average == Decimal("84.00"), "the viewed term must be unchanged"
    assert card.sessional_terms_counted == 2
    assert card.sessional_score == Decimal("74.00")          # (84 + 64) / 2
    got = {t.term_name: t.average for t in card.sessional_terms}
    assert got == {"Autumn": Decimal("84.00"), "Spring": Decimal("64.00")}
    row = next(r for r in card.subjects if r.subject_name == "Mathematics")
    assert row.sessional == Decimal("74.00")


async def test_an_unmarked_term_is_reported_not_counted(db, org):
    """Summer exists and has a cumulative but no marks. It must appear in the
    breakdown with a null average and must not drag the mean down."""
    admin, terms, full, maths, pupil = await _session(
        db, org, ["Autumn", "Spring", "Summer"])
    autumn, spring, _summer = terms
    await _enter(db, admin, pupil, maths, autumn, (18, 16, 8, 9, 50))   # 84
    await _enter(db, admin, pupil, maths, spring, (10, 10, 5, 5, 44))   # 64

    card = await report_card(student_id=pupil.id, term_id=autumn.id,
                             sub_term_id=full.id, db=db, current_user=admin)

    assert card.sessional_score == Decimal("74.00"), "not (84+64+0)/3 = 49.33"
    assert card.sessional_terms_counted == 2
    assert len(card.sessional_terms) == 3
    assert next(t.average for t in card.sessional_terms if t.term_name == "Summer") is None


async def test_one_marked_term_reports_no_sessional_score(db, org):
    """A mean of one term is that term's average. Publishing it as a Sessional
    Score would be the same number under a name that claims more."""
    admin, terms, full, maths, pupil = await _session(db, org, ["Autumn", "Spring"])
    autumn, _spring = terms
    await _enter(db, admin, pupil, maths, autumn, (18, 16, 8, 9, 50))

    card = await report_card(student_id=pupil.id, term_id=autumn.id,
                             sub_term_id=full.id, db=db, current_user=admin)

    assert card.average == Decimal("84.00")
    assert card.sessional_score is None
    assert card.sessional_terms_counted == 1
    row = next(r for r in card.subjects if r.subject_name == "Mathematics")
    assert row.sessional is None


async def test_other_terms_assessments_do_not_leak_into_the_columns(db, org):
    admin, terms, full, maths, pupil = await _session(db, org, ["Autumn", "Spring"])
    autumn, spring = terms
    await _enter(db, admin, pupil, maths, autumn, (18, 16, 8, 9, 50))
    await _enter(db, admin, pupil, maths, spring, (10, 10, 5, 5, 44))

    card = await report_card(student_id=pupil.id, term_id=autumn.id,
                             sub_term_id=full.id, db=db, current_user=admin)

    autumn_ids = {a.id for a in await list_assessments(
        term_id=autumn.id, db=db, current_user=admin)}
    spring_ids = {a.id for a in await list_assessments(
        term_id=spring.id, db=db, current_user=admin)}
    keys = {c.key for c in card.columns}
    assert not (keys & spring_ids), "a Spring assessment appeared on an Autumn card"
    assert keys & autumn_ids
    # One TOTAL column, not one per term.
    assert [c.name for c in card.columns].count("TOTAL") == 1
