"""Secondary Report parity S-4a: cumulative evaluator + Report Entry round-trip."""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.school import Subject, SchoolClass, Student
from app.models.modules.platform import AcademicTerm, AcademicSubTerm
from app.services.report_engine import evaluate_cumulative, round_dp
from app.routers.modules.platform import (
    bootstrap_assessments, bootstrap_cumulatives, list_assessments,
    report_entry_grid, save_report_entry,
)
from app.schemas.platform import ReportEntrySave, ScoreItem


pytestmark = pytest.mark.asyncio


# ── Pure evaluator (no DB) ───────────────────────────────────────────────────

def test_evaluator_curated_composition():
    A = {
        "cbt": SimpleNamespace(max_score=Decimal("20")),
        "thy": SimpleNamespace(max_score=Decimal("20")),
        "prj": SimpleNamespace(max_score=Decimal("10")),
        "pbt": SimpleNamespace(max_score=Decimal("10")),
        "exam": SimpleNamespace(max_score=Decimal("60")),
    }
    C = {
        "htt": SimpleNamespace(cumul_type="score", max_percent=None),
        "pct": SimpleNamespace(cumul_type="percentage", max_percent=None),
        "ca1": SimpleNamespace(cumul_type="custom_percentage", max_percent=Decimal("20")),
        "total": SimpleNamespace(cumul_type="score", max_percent=None),
    }
    comps = {
        "htt": [("assessment", "cbt"), ("assessment", "thy")],
        "pct": [("assessment", "cbt"), ("assessment", "thy")],
        "ca1": [("cumulative", "htt")],
        "total": [("cumulative", "ca1"), ("assessment", "prj"), ("assessment", "pbt"), ("assessment", "exam")],
    }
    scores = {"cbt": Decimal("18"), "thy": Decimal("16"), "prj": Decimal("8"), "pbt": Decimal("9"), "exam": Decimal("50")}

    htt_v, htt_m = evaluate_cumulative("htt", C, comps, A, scores)
    assert htt_v == Decimal("34") and htt_m == Decimal("40")
    pct_v, pct_m = evaluate_cumulative("pct", C, comps, A, scores)
    assert pct_v == Decimal("85") and pct_m == Decimal("100")     # 34/40*100
    ca1_v, ca1_m = evaluate_cumulative("ca1", C, comps, A, scores)
    assert ca1_v == Decimal("17") and ca1_m == Decimal("20")      # 34/40*20
    total_v, total_m = evaluate_cumulative("total", C, comps, A, scores)
    assert total_v == Decimal("84") and total_m == Decimal("100")  # 17+8+9+50

    # Missing scores default to 0; empty maxes don't divide-by-zero.
    assert evaluate_cumulative("pct", C, comps, A, {})[0] == Decimal("0")
    assert round_dp(Decimal("84.567"), 2) == Decimal("84.57")


def test_evaluator_cycle_guard():
    C = {"a": SimpleNamespace(cumul_type="score", max_percent=None),
         "b": SimpleNamespace(cumul_type="score", max_percent=None)}
    comps = {"a": [("cumulative", "b")], "b": [("cumulative", "a")]}
    # Should terminate, not recurse forever.
    assert evaluate_cumulative("a", C, comps, {}, {}) == (Decimal("0"), Decimal("0"))


# ── Report Entry round-trip (DB) ─────────────────────────────────────────────

async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Teacher",
             status=UserStatus.ACTIVE, org_id=org.id)
    _r = Role(id=str(uuid.uuid4()), name="admin", slug="super_user", permissions=["*"], org_id=org.id, is_system=False)
    db.add(_r)
    u.roles = [_r]
    db.add(u)
    await db.commit()
    return u


async def test_report_entry_round_trip(db, org):
    admin = await _admin(db, org)
    autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 7A", level="YEAR 7", org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    s1 = Student(id=str(uuid.uuid4()), student_id="FS/1", first_name="Ada", last_name="Obi", class_id=cls.id, org_id=org.id)
    db.add_all([autumn, half, full, cls, subj, s1])
    await db.commit()

    await bootstrap_assessments(db=db, current_user=admin)
    asmts = await list_assessments(term_id=autumn.id, db=db, current_user=admin)
    cbt = next(a for a in asmts if a.name == "CBT")

    grid = await report_entry_grid(class_id=cls.id, subject_id=subj.id, term_id=autumn.id, db=db, current_user=admin)
    assert len(grid.students) == 1 and grid.students[0].name == "Ada Obi"
    assert {a.name for a in grid.assessments} == {"CBT", "THEORY", "PRJ", "PBT", "EXAM"}
    assert grid.scores[s1.id] == {}    # nothing entered yet

    await save_report_entry(payload=ReportEntrySave(subject_id=subj.id, items=[
        ScoreItem(student_id=s1.id, assessment_id=cbt.id, score=Decimal("18"))]), db=db, current_user=admin)

    grid2 = await report_entry_grid(class_id=cls.id, subject_id=subj.id, term_id=autumn.id, db=db, current_user=admin)
    assert grid2.scores[s1.id][cbt.id] == Decimal("18")

    # Re-save updates in place (no duplicate row).
    await save_report_entry(payload=ReportEntrySave(subject_id=subj.id, items=[
        ScoreItem(student_id=s1.id, assessment_id=cbt.id, score=Decimal("20"))]), db=db, current_user=admin)
    grid3 = await report_entry_grid(class_id=cls.id, subject_id=subj.id, term_id=autumn.id, db=db, current_user=admin)
    assert grid3.scores[s1.id][cbt.id] == Decimal("20")
