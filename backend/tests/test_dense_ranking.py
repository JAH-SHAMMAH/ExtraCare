"""One ranking rule: dense, by average, compared at the printed precision.

Three implementations disagreed before this. The broadsheet and the card both
ranked ordinally by TOTAL; the Order of Merit ranked by AVERAGE with standard
competition ranking (1, 2, 2, 4). So a pupil's position on their own card could
differ from the same pupil's position on their class's broadsheet, and differ
again on the merit list.

THE SAMPLE THAT SETTLES IT. Educare's saved Secondary report shows two pupils
tied at 888.00 / 88.80 both printing "5th", and the next distinct average
printing "6th". Competition ranking would have printed "7th".
`test_the_educare_sample` is that page, as a test.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.services.ranking import (
    PLACES, dense_positions, position_of, tied_positions,
)


def D(x) -> Decimal:
    return Decimal(str(x))


# ── the rule ────────────────────────────────────────────────────────────────

def test_the_educare_sample():
    """Two pupils tie at 88.80 and both come 5th; the next distinct average is
    6th, NOT 7th. The whole phase exists for this one assertion."""
    averages = {
        "a": D("95.10"), "b": D("93.40"), "c": D("91.20"), "d": D("90.05"),
        "e": D("88.80"), "f": D("88.80"),          # the tie
        "g": D("87.60"),                            # must be 6th
    }
    pos = dense_positions(averages)
    assert pos["e"] == 5 and pos["f"] == 5, "the tied pair must share a position"
    assert pos["g"] == 6, (
        "dense ranking: the pupil after a tie is NOT skipped past. Competition "
        "ranking would put them 7th, which is what this replaced"
    )


def test_dense_not_competition_across_several_ties():
    pos = dense_positions({
        "a": D(90), "b": D(90), "c": D(90),   # three-way tie -> all 1st
        "d": D(80),                            # -> 2nd
        "e": D(70), "f": D(70),                # -> 3rd
        "g": D(60),                            # -> 4th
    })
    assert [pos[k] for k in "abc"] == [1, 1, 1]
    assert pos["d"] == 2
    assert pos["e"] == pos["f"] == 3
    assert pos["g"] == 4
    assert max(pos.values()) == 4, "positions must be gap-free"


def test_best_first():
    pos = dense_positions({"low": D(10), "high": D(90), "mid": D(50)})
    assert (pos["high"], pos["mid"], pos["low"]) == (1, 2, 3)


# ── compared at the printed precision ───────────────────────────────────────

def test_averages_that_print_the_same_must_tie():
    """THE OLD BUG. The Order of Merit compared raw averages, so two values that
    both display as 88.80 were ranked 5th and 6th -- two identical printed
    numbers in different places, which is exactly what a parent queries."""
    pos = dense_positions({"a": D("88.7951"), "b": D("88.8049")})
    assert pos["a"] == pos["b"] == 1, (
        "both round to 88.80 at the printed precision, so they tie"
    )


def test_a_difference_above_the_printed_precision_does_not_tie():
    pos = dense_positions({"a": D("88.80"), "b": D("88.79")})
    assert pos["a"] == 1 and pos["b"] == 2


def test_rounding_is_round_dp_not_python_round():
    """`round_dp` is Decimal ROUND_HALF_UP; python's round() is banker's rounding
    and sends an exact .5 to the nearer EVEN digit. 88.125 is exactly
    representable in binary, so it is a case where the two genuinely disagree --
    half-up gives 88.13, python gives 88.12.

    The project rule is round_dp everywhere a figure is compared or printed, and
    a ranker using python's round() would place a pupil differently from the way
    their own average prints.
    """
    from app.services.report_engine import round_dp
    assert round_dp(D("88.125"), 2) == D("88.13"), "half-up"
    assert round(88.125, 2) == 88.12, "python rounds to even -- the divergence"

    # The ranker follows round_dp, so 88.125 ties with 88.13 and NOT with 88.12.
    assert dense_positions({"a": D("88.125"), "b": D("88.13")}) == {"a": 1, "b": 1}
    split = dense_positions({"a": D("88.125"), "b": D("88.12")})
    assert split["a"] == 1 and split["b"] == 2


def test_places_is_the_printed_precision():
    assert PLACES == 2


# ── an unmarked pupil is not ranked ─────────────────────────────────────────

def test_unmarked_pupils_are_omitted_not_placed_last():
    """Their standing is unknown, not bottom. A merit list that placed them
    would be inventing a result for a child."""
    pos = dense_positions({"marked": D(70), "unmarked": None})
    assert pos == {"marked": 1}
    assert "unmarked" not in pos


def test_all_unmarked():
    assert dense_positions({"a": None, "b": None}) == {}


def test_empty():
    assert dense_positions({}) == {}


def test_position_of_returns_zero_for_unranked():
    """0, not None: it is what BroadsheetRow.position and the card already
    default to, so an unranked pupil needs no new representation."""
    vals = {"a": D(90), "b": None}
    assert position_of("a", vals) == 1
    assert position_of("b", vals) == 0
    assert position_of("nobody", vals) == 0


# ── tie flagging ────────────────────────────────────────────────────────────

def test_tied_positions():
    pos = dense_positions({"a": D(90), "b": D(90), "c": D(80)})
    shared = tied_positions(pos)
    assert shared == {1}
    assert pos["c"] not in shared


def test_no_ties():
    assert tied_positions(dense_positions({"a": D(90), "b": D(80)})) == set()


# ── order independence ──────────────────────────────────────────────────────

def test_insertion_order_does_not_matter():
    """A mapping built from a database read arrives in whatever order the planner
    chose; the positions must not depend on it."""
    forward = dense_positions({"a": D(90), "b": D(80), "c": D(80), "d": D(70)})
    reverse = dense_positions({"d": D(70), "c": D(80), "b": D(80), "a": D(90)})
    assert forward == reverse


# ── the endpoints agree ─────────────────────────────────────────────────────

pytestmark_db = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_card_and_broadsheet_agree_on_position(db, org):
    """THE CROSS-CHECK. These two disagreed before: the broadsheet numbered rows
    1..n by total, the card took an index into a total-sorted list. Same class,
    same term -- the numbers must match for every pupil."""
    from decimal import Decimal as Dec

    from app.models.modules.platform import (
        AcademicSubTerm, AcademicTerm, Assessment, Cumulative, CumulativeComponent,
        GradingBand, GradingScale, StudentAssessmentScore,
    )
    from app.models.modules.school import SchoolClass, Student, Subject
    from app.models.role import Role
    from app.models.user import User, UserStatus
    from app.routers.modules.platform import report_broadsheet, report_card
    from tests.conftest import ensure_section, ensure_session

    session = await ensure_session(db, org)
    admin = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com",
                 full_name="Officer", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="admin", slug="super_user",
                permissions=["*"], org_id=org.id, is_system=False)
    db.add(role)
    admin.roles = [role]
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    sec = await ensure_section(db, org)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10 A", level="Year 10",
                      section_id=sec.id, org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=sec.id, org_id=org.id)
    eng = Subject(id=str(uuid.uuid4()), name="English", section_id=sec.id, org_id=org.id)
    db.add_all([admin, term, full, cls, maths, eng])
    await db.commit()

    scale = GradingScale(id=str(uuid.uuid4()), name="GRADING SCALE", scale_type="numeric",
                         is_provisional=False, purpose="grade", show_in_table=True,
                         org_id=org.id)
    db.add(scale)
    await db.flush()
    for g, lo, hi in [("A", 80, 100), ("B", 60, 79), ("F", 0, 59)]:
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=scale.id, grade=g,
                           min_score=Dec(lo), max_score=Dec(hi), org_id=org.id))

    exam = Assessment(id=str(uuid.uuid4()), name="Exam", max_score=Dec(100),
                      session_id=session.id, term_id=term.id, sub_term_id=full.id,
                      org_id=org.id)
    db.add(exam)
    await db.flush()
    total_col = Cumulative(id=str(uuid.uuid4()), name="TOTAL", session_id=session.id,
                           term_id=term.id, sub_term_id=full.id, cumul_type="score",
                           org_id=org.id)
    db.add(total_col)
    await db.flush()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), org_id=org.id,
                               cumulative_id=total_col.id, ref_type="assessment",
                               ref_id=exam.id, position=0))

    # Three pupils. TWO TIE on average while differing on total, because one of
    # them sat only one subject -- the case where ranking by total and ranking by
    # average give different answers.
    pupils = {}
    for i, (name, marks) in enumerate([
        ("Top",  {maths.id: 90, eng.id: 90}),     # avg 90, total 180
        ("Tie",  {maths.id: 90}),                  # avg 90, total  90  <- same avg
        ("Low",  {maths.id: 70, eng.id: 70}),     # avg 70, total 140
    ]):
        p = Student(id=str(uuid.uuid4()), student_id=f"FSS/24/{100+i}",
                    first_name=name, last_name="Pupil", class_id=cls.id, org_id=org.id)
        db.add(p)
        pupils[name] = p
        await db.flush()
        for sid, score in marks.items():
            db.add(StudentAssessmentScore(id=str(uuid.uuid4()), org_id=org.id,
                                          student_id=p.id, subject_id=sid,
                                          assessment_id=exam.id, score=Dec(score)))
    await db.commit()

    bs = await report_broadsheet(class_id=cls.id, term_id=term.id,
                                 sub_term_id=full.id, db=db, current_user=admin)
    by_id = {r.student_id: r for r in bs.rows}

    # Ranked by AVERAGE, so the two 90-average pupils tie despite totals of
    # 180 and 90. Ranking by total would have separated them.
    assert by_id[pupils["Top"].id].position == 1
    assert by_id[pupils["Tie"].id].position == 1, (
        "ranked by total, this pupil came after Top; by average they tie"
    )
    assert by_id[pupils["Low"].id].position == 2, "dense: 1, 1, 2 -- not 1, 2, 3"

    for name, p in pupils.items():
        card = await report_card(student_id=p.id, term_id=term.id,
                                 sub_term_id=full.id, db=db, current_user=admin)
        assert card.position == by_id[p.id].position, (
            f"{name}: card says {card.position}, broadsheet says "
            f"{by_id[p.id].position} -- these two disagreed before this phase"
        )
