"""A sub-term with no columns says so, instead of borrowing another's.

~~~ THE LIVE DEFECT THIS CLOSES ~~~
`_pick_display_cumulative` used to end with a fallback: when the requested
sub-term had no column of its own, it returned ANY cumulative of the term. The
Result tracker had already discovered what that does and worked around it
locally rather than fixing it — its comment reads "it made the Autumn Half-Term
column repeat the Full-Term mark, which asserts a half-term score nobody
recorded."

That was not hypothetical. Fairview's ACTIVE term is Summer with Half-Term as
its active sub-term, and NO term has a Half-Term column at all — measured
against both the head-138 dump and the live database. So a card opened for the
active term printed the FULL-TERM figure under a HALF-TERM heading, and a parent
reading it had no way to tell.

`test_the_live_summer_half_term_shape` is that exact configuration. The
assertion that matters is not the flag — it is that `total` and `average` are
NOT the Full-Term numbers.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, Cumulative, CumulativeComponent,
    GradingBand, GradingScale, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import (
    _pick_display_cumulative, report_broadsheet, report_card,
)
from tests.conftest import ensure_section, ensure_session

pytestmark = pytest.mark.asyncio


# ── the picker itself, as a pure function ───────────────────────────────────

class _Cumul:
    def __init__(self, name, sub_term_id, position=0):
        self.id = f"c-{name}-{sub_term_id}"
        self.name, self.sub_term_id, self.position = name, sub_term_id, position


def test_picker_returns_none_rather_than_another_sub_terms_column():
    """THE FIX, in isolation. A Full-Term TOTAL must not be offered as the
    Half-Term display column."""
    full = [_Cumul("TOTAL", "full")]
    assert _pick_display_cumulative(full, "full") is not None
    assert _pick_display_cumulative(full, "half") is None, (
        "the Full-Term column was returned for Half-Term — the borrow that "
        "printed a half-term score nobody recorded"
    )


def test_picker_still_prefers_total_within_the_right_sub_term():
    """The behaviour that was correct is unchanged: TOTAL wins over a
    higher-positioned sibling in the SAME sub-term."""
    rows = [_Cumul("CA", "full", position=9), _Cumul("TOTAL", "full", position=1)]
    assert _pick_display_cumulative(rows, "full").name == "TOTAL"


def test_picker_falls_back_by_position_within_the_right_sub_term():
    rows = [_Cumul("CA", "full", position=1), _Cumul("Exam", "full", position=5)]
    assert _pick_display_cumulative(rows, "full").name == "Exam"


def test_picker_on_an_empty_set():
    assert _pick_display_cumulative([], "full") is None


# ── the endpoints ───────────────────────────────────────────────────────────

class W:
    pass


async def _world(db, org) -> W:
    """Fairview's live shape: columns on Full-Term only, marks entered, and a
    Half-Term sub-term that nothing is configured for."""
    w = W()
    w.session = await ensure_session(db, org)
    w.admin = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com",
                   full_name="Officer", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="admin", slug="super_user",
                permissions=["*"], org_id=org.id, is_system=False)
    db.add(role)
    w.admin.roles = [role]

    w.term = AcademicTerm(id=str(uuid.uuid4()), name="Summer", position=3, org_id=org.id)
    w.half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    w.full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    sec = await ensure_section(db, org)
    w.cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10 A", level="Year 10",
                        section_id=sec.id, org_id=org.id)
    w.subject = Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=sec.id, org_id=org.id)
    w.pupil = Student(id=str(uuid.uuid4()), student_id="FSS/24/119", first_name="Chi",
                      last_name="Okeke", class_id=w.cls.id, org_id=org.id)
    db.add_all([w.admin, w.term, w.half, w.full, w.cls, w.subject, w.pupil])
    await db.commit()

    scale = GradingScale(id=str(uuid.uuid4()), name="GRADING SCALE", scale_type="numeric",
                         is_provisional=False, purpose="grade", show_in_table=True, org_id=org.id)
    db.add(scale)
    await db.flush()
    for grade, lo, hi in [("A", 90, 100), ("C", 70, 89), ("F", 0, 69)]:
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=scale.id, grade=grade,
                           min_score=Decimal(lo), max_score=Decimal(hi), org_id=org.id))

    # Columns on FULL-TERM ONLY — the production shape.
    w.exam = Assessment(id=str(uuid.uuid4()), name="Exam", max_score=Decimal(100),
                        session_id=w.session.id, term_id=w.term.id,
                        sub_term_id=w.full.id, org_id=org.id)
    db.add(w.exam)
    await db.flush()
    w.total = Cumulative(id=str(uuid.uuid4()), name="TOTAL", session_id=w.session.id,
                         term_id=w.term.id, sub_term_id=w.full.id,
                         cumul_type="score", org_id=org.id)
    db.add(w.total)
    await db.flush()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), org_id=org.id,
                               cumulative_id=w.total.id, ref_type="assessment",
                               ref_id=w.exam.id, position=0))
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), org_id=org.id,
                                  student_id=w.pupil.id, subject_id=w.subject.id,
                                  assessment_id=w.exam.id, score=Decimal(88)))
    await db.commit()
    return w


async def test_the_configured_sub_term_is_unaffected(db, org):
    """The control. Full-Term has a column and real marks, so nothing about this
    change may touch it."""
    w = await _world(db, org)
    card = await report_card(student_id=w.pupil.id, term_id=w.term.id,
                             sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert card.not_configured is False
    assert card.total == Decimal("88.00")
    assert len(card.columns) == 2          # the Exam assessment + the TOTAL column


async def test_the_live_summer_half_term_shape(db, org):
    """THE DEFECT. Same term, same pupil, same marks — but asked for the sub-term
    that nothing is configured for.

    The flag is the lesser assertion. The one that matters is that the figures
    are NOT the Full-Term's: an 88 appearing here is the borrow, and it would be
    printed under a "Half-Term" heading on a parent's card.
    """
    w = await _world(db, org)
    card = await report_card(student_id=w.pupil.id, term_id=w.term.id,
                             sub_term_id=w.half.id, db=db, current_user=w.admin)

    assert card.not_configured is True
    assert card.total != Decimal("88.00"), (
        "the Half-Term card borrowed the Full-Term figure — this is the exact "
        "defect, and a parent could not have told"
    )
    assert card.total == Decimal("0.00")
    assert card.average == Decimal("0.00")
    assert card.columns == []

    # The subject row IS still emitted, and that is correct: `load_term_setup`
    # loads the whole TERM, so the pupil's Full-Term Exam mark puts Mathematics
    # in the subject list. What matters is that the row carries NOTHING — no
    # values, no grade, no arm average — rather than the Full-Term figures under
    # a Half-Term heading. With `not_configured` set, the page shows the
    # "not set up" panel instead of the table anyway.
    for row in card.subjects:
        assert row.values == {}, f"{row.subject_name} borrowed a value"
        assert row.grade is None
        assert row.subject_arm_average is None


async def test_the_broadsheet_reports_it_too(db, org):
    """Same condition, the other reader. Its old empty state said "No results —
    enter marks under Report Entry first", which blames the teachers for marks
    that have nowhere to land."""
    w = await _world(db, org)

    ok = await report_broadsheet(class_id=w.cls.id, term_id=w.term.id,
                                 sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert ok.not_configured is False

    bad = await report_broadsheet(class_id=w.cls.id, term_id=w.term.id,
                                  sub_term_id=w.half.id, db=db, current_user=w.admin)
    assert bad.not_configured is True
    assert bad.display_cumulative is None
    assert all(r.total == Decimal("0.00") for r in bad.rows)


async def test_a_term_with_no_columns_at_all(db, org):
    """Neither sub-term configured — the state Fairview's Autumn and Spring were
    in before Report Setup was filled, and the one that made every subject grade
    F. It must report "not configured", never a computed zero."""
    w = await _world(db, org)
    bare = AcademicTerm(id=str(uuid.uuid4()), name="Spring", position=2, org_id=org.id)
    db.add(bare)
    await db.commit()

    card = await report_card(student_id=w.pupil.id, term_id=bare.id,
                             sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert card.not_configured is True
    assert card.subjects == []


async def test_not_configured_is_false_by_default_on_the_schema(db, org):
    """The field defaults to False, so an older client that does not know about
    it keeps its current behaviour rather than seeing every card as broken."""
    from app.schemas.platform import BroadsheetResponse, ReportCardResponse

    assert ReportCardResponse(student_id="x").not_configured is False
    assert BroadsheetResponse(class_id="x").not_configured is False
