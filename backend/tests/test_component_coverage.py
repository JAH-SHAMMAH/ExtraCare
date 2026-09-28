"""A class cannot be published while a component of its TOTAL is unmarked.

The arithmetic that makes this necessary: `evaluate_cumulative` reads a missing
score as `Decimal(0)` and still counts the component's full `max_score` in the
denominator. Under CA(40) + Exam(60) with no CA marks, a pupil who scored 100%
on the exam prints as 60% — a D. Measured against the real Autumn data before
this was written, those weights would have moved 1,645 of 1,799 letters.

So the gate refuses, and these pin the three cases that matter:
  * Spring-shaped: exam marked, CA not -> refused, naming CA;
  * fully marked   -> publishes;
  * Autumn-shaped: a TOTAL of ONE assessment everyone has -> unaffected, which
    is what keeps the twelve already-published classes publishable.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.academics import ReportApproval
from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, Cumulative, CumulativeComponent,
    StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.academics import update_report_workflow
from app.schemas.academics import ReportApprovalUpdate
from app.services.component_coverage import component_coverage


async def _admin(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="org_admin", slug=f"a-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Admin", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _world(db, org, *, weighted: bool, mark_ca: bool):
    """A class, two pupils, one subject, and a term whose TOTAL is either
    CA(40)+Exam(60) (`weighted`) or the single assessment Autumn uses."""
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Spring" if weighted else "Autumn",
                        position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    db.add_all([cls, subj, term, full])
    await db.commit()

    pupils = [Student(id=str(uuid.uuid4()), student_id=f"S-{i}", first_name=f"P{i}",
                      last_name="Test", class_id=cls.id, org_id=org.id) for i in (1, 2)]
    db.add_all(pupils)
    await db.commit()

    exam = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", max_score=100,
                      term_id=term.id, sub_term_id=full.id, org_id=org.id)
    db.add(exam)
    await db.commit()

    if weighted:
        ca = Assessment(id=str(uuid.uuid4()), name="Continuous Assessment", max_score=40,
                        term_id=term.id, sub_term_id=full.id, org_id=org.id)
        db.add(ca)
        await db.commit()
        ca_c = Cumulative(id=str(uuid.uuid4()), name="CA", cumul_type="custom_percentage",
                          max_percent=40, term_id=term.id, sub_term_id=full.id, org_id=org.id)
        ex_c = Cumulative(id=str(uuid.uuid4()), name="Exam", cumul_type="custom_percentage",
                          max_percent=60, term_id=term.id, sub_term_id=full.id, org_id=org.id)
        total = Cumulative(id=str(uuid.uuid4()), name="TOTAL", cumul_type="percentage",
                           term_id=term.id, sub_term_id=full.id, position=2, org_id=org.id)
        db.add_all([ca_c, ex_c, total])
        await db.commit()
        db.add_all([
            CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=ca_c.id,
                                ref_type="assessment", ref_id=ca.id, position=0, org_id=org.id),
            CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=ex_c.id,
                                ref_type="assessment", ref_id=exam.id, position=0, org_id=org.id),
            CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=total.id,
                                ref_type="cumulative", ref_id=ca_c.id, position=0, org_id=org.id),
            CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=total.id,
                                ref_type="cumulative", ref_id=ex_c.id, position=1, org_id=org.id),
        ])
    else:
        ca = None
        total = Cumulative(id=str(uuid.uuid4()), name="TOTAL", cumul_type="percentage",
                           term_id=term.id, sub_term_id=full.id, org_id=org.id)
        db.add(total)
        await db.commit()
        db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=total.id,
                                   ref_type="assessment", ref_id=exam.id, position=0,
                                   org_id=org.id))
    await db.commit()

    # Everyone has the exam mark; CA only when asked for.
    for p in pupils:
        db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=p.id,
                                      subject_id=subj.id, assessment_id=exam.id,
                                      score=100, org_id=org.id))
        if ca is not None and mark_ca:
            db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=p.id,
                                          subject_id=subj.id, assessment_id=ca.id,
                                          score=30, org_id=org.id))
    await db.commit()
    return dict(cls=cls, subj=subj, term=term, full=full, pupils=pupils)


# ── the coverage report itself ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_it_names_the_unmarked_component(db, org):
    w = await _world(db, org, weighted=True, mark_ca=False)
    cov = await component_coverage(db, org.id, w["term"].id, w["full"].id, w["cls"].id)

    assert cov.ok is False
    assert sorted(cov.required) == ["CBT Exam Score", "Continuous Assessment"]
    assert {m.assessment_name for m in cov.missing} == {"Continuous Assessment"}
    assert len(cov.pupils_affected) == 2
    msg = cov.message()
    assert "Continuous Assessment" in msg
    assert "counted as zero" in msg
    assert "P1 Test" in msg, "a count alone sends someone hunting"
    # The refusal must not reach for vocabulary this product does not have.
    for word in ("plan", "tier", "upgrade", "subscription"):
        assert word not in msg.lower()


@pytest.mark.asyncio
async def test_a_fully_marked_class_is_clear(db, org):
    w = await _world(db, org, weighted=True, mark_ca=True)
    cov = await component_coverage(db, org.id, w["term"].id, w["full"].id, w["cls"].id)
    assert cov.ok is True
    assert cov.missing == []


@pytest.mark.asyncio
async def test_a_single_component_total_is_unaffected(db, org):
    """Autumn's shape: TOTAL is one assessment and every pupil has it. The twelve
    classes already published must stay publishable."""
    w = await _world(db, org, weighted=False, mark_ca=False)
    cov = await component_coverage(db, org.id, w["term"].id, w["full"].id, w["cls"].id)
    assert cov.ok is True
    assert cov.required == ["CBT Exam Score"]


@pytest.mark.asyncio
async def test_a_term_with_no_cumulative_is_not_reported_as_missing(db, org):
    """Nothing to compute means nothing can be missing; refusing would be nonsense
    and would block a school that simply has not set the term up yet."""
    cls = SchoolClass(id=str(uuid.uuid4()), name="X", level="Secondary", org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Summer", org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
    db.add_all([cls, term, full])
    await db.commit()

    cov = await component_coverage(db, org.id, term.id, full.id, cls.id)
    assert cov.not_configured is True
    assert cov.ok is True


@pytest.mark.asyncio
async def test_a_pupil_with_no_marks_at_all_is_not_listed(db, org):
    """Unassessed in a subject is a different situation from part-marked, and is
    not fixed by entering one component. Listing them buries the real gaps."""
    w = await _world(db, org, weighted=True, mark_ca=True)
    extra = Student(id=str(uuid.uuid4()), student_id="S-9", first_name="Unmarked",
                    last_name="Pupil", class_id=w["cls"].id, org_id=org.id)
    db.add(extra)
    await db.commit()

    cov = await component_coverage(db, org.id, w["term"].id, w["full"].id, w["cls"].id)
    assert cov.ok is True
    assert extra.id not in cov.pupils_affected


# ── the publish gate ──────────────────────────────────────────────────────────

async def _workflow(db, org, cls, term, stage="approved") -> ReportApproval:
    r = ReportApproval(id=str(uuid.uuid4()), class_id=cls.id, term_id=term.id,
                       stage=stage, org_id=org.id)
    db.add(r)
    await db.commit()
    return r


@pytest.mark.asyncio
async def test_publish_is_refused_while_a_component_is_unmarked(db, org):
    w = await _world(db, org, weighted=True, mark_ca=False)
    admin = await _admin(db, org)
    r = await _workflow(db, org, w["cls"], w["term"])

    with pytest.raises(HTTPException) as e:
        await update_report_workflow(r.id, ReportApprovalUpdate(stage="published"),
                                     request=None, db=db, current_user=admin)
    assert e.value.status_code == 422
    assert "Continuous Assessment" in str(e.value.detail)

    await db.refresh(r)
    assert r.stage == "approved", "the stage must not move when the publish is refused"
    assert r.published_at is None


@pytest.mark.asyncio
async def test_publish_succeeds_once_every_component_is_marked(db, org):
    w = await _world(db, org, weighted=True, mark_ca=True)
    admin = await _admin(db, org)
    r = await _workflow(db, org, w["cls"], w["term"])

    await update_report_workflow(r.id, ReportApprovalUpdate(stage="published"),
                                 request=None, db=db, current_user=admin)
    await db.refresh(r)
    assert r.stage == "published"
    assert r.published_at is not None


@pytest.mark.asyncio
async def test_an_autumn_shaped_class_still_publishes(db, org):
    """The regression that would matter most: the guard must not lock the twelve
    classes whose cards are already out."""
    w = await _world(db, org, weighted=False, mark_ca=False)
    admin = await _admin(db, org)
    r = await _workflow(db, org, w["cls"], w["term"])

    await update_report_workflow(r.id, ReportApprovalUpdate(stage="published"),
                                 request=None, db=db, current_user=admin)
    await db.refresh(r)
    assert r.stage == "published"
