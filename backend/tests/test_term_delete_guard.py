"""Deleting or renaming a term must say what it will break, and leave a record.

Written from an incident. In September 2026 a term was removed during a Report
Setup rebuild. `assessments.term_id` is ON DELETE CASCADE and
`student_assessment_scores.assessment_id` is too, so the CBT assessment and
every score beneath it went with it. Nothing warned beforehand and nothing was
recorded afterwards — there was no audit row naming who had done it. Teachers
discovered it when Make Report came up empty, and the repair took a five-table
re-tag of 2,113 rows plus a re-sync of 1,799 score rows.

Two kinds of damage, and the warning has to name both:

  HARD — rows the database CASCADE deletes. Visible in the schema.
  SOFT — rows that merely stop MATCHING. Term is free text in five other tables,
         compared by value, so nothing is deleted and nothing errors: the CBT
         sync stops resolving, the publish freeze stops firing, and the parent
         report-card gate starts refusing everyone. This is the half that
         actually caused the incident, and no schema-level check would mention
         it.

A rename is pinned too, because it strands the soft rows exactly as a delete
does while looking far more innocent.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.modules.academics import ReportApproval
from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, StudentAssessmentScore,
)
from app.models.modules.school import CBTExam, ExamStatus, SchoolClass, Student, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import create_term, delete_term, update_term
from app.schemas.platform import TermCreate, TermUpdate
from tests.conftest import ensure_session
from tests.conftest import ensure_section

TERM = "Autumn"


async def _admin(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="admin", slug=f"a-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Admin", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _bare_term(db, org, name=TERM) -> AcademicTerm:
    t = AcademicTerm(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(t)
    await db.commit()
    return t


async def _term_with_hard_rows(db, org):
    """A term with an assessment and a score — both CASCADE on delete."""
    t = await _bare_term(db, org)
    sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    _sec = await ensure_section(db, org)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=_sec.id, org_id=org.id)
    db.add_all([sub, cls, subj])
    await db.commit()

    _sess = await ensure_session(db, org)
    a = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", max_score=100,
                   session_id=_sess.id, term_id=t.id, sub_term_id=sub.id, org_id=org.id)
    stu = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="A", last_name="B",
                  class_id=cls.id, org_id=org.id)
    db.add_all([a, stu])
    await db.commit()
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=stu.id,
                                  subject_id=subj.id, assessment_id=a.id,
                                  score=72, org_id=org.id))
    await db.commit()
    return t, cls, subj


async def _term_with_soft_rows(db, org):
    """Rows that name the term by VALUE, plus one that points at it by KEY.

    The ReportApproval here used to be soft (name-matched). Migration 131 gave it a
    term_id FK with ON DELETE CASCADE, so it is now HARD damage — it is destroyed
    rather than stranded. Kept in this fixture deliberately, so the test below can
    assert that the warning puts each row in the right half.

    The CBT exam moved too, in migration 132, but only halfway: term_id with ON
    DELETE SET NULL. So a DELETE still leaves it behind (soft), while a RENAME no
    longer touches it at all — which is what the rename test below now pins.
    """
    t = await _bare_term(db, org)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    _sec = await ensure_section(db, org)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=_sec.id, org_id=org.id)
    db.add_all([cls, subj])
    await db.commit()
    db.add_all([
        CBTExam(id=str(uuid.uuid4()), title="Maths CBT", status=ExamStatus.PUBLISHED,
                total_points=10, class_id=cls.id, subject_id=subj.id, term_id=t.id,
                created_by=(await _admin(db, org)).id, org_id=org.id),
        # Keyed by term_id since migration 131. Note this now makes the
        # approval a real dependent of the term row, which is exactly what
        # the delete guard is about.
        ReportApproval(id=str(uuid.uuid4()), class_id=cls.id, term_id=t.id,
                       stage="published", org_id=org.id),
    ])
    await db.commit()
    return t


# ── the guard ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_term_with_nothing_attached_deletes_without_ceremony(db, org):
    """The guard must not become a nuisance on an empty term, or it gets
    click-through'd on the one that matters."""
    admin = await _admin(db, org)
    t = await _bare_term(db, org)

    await delete_term(t.id, confirm=False, request=None, db=db, current_user=admin)

    assert (await db.execute(select(AcademicTerm))).scalars().first() is None


@pytest.mark.asyncio
async def test_deleting_a_term_with_assessments_is_refused_and_counts_them(db, org):
    admin = await _admin(db, org)
    t, _, _ = await _term_with_hard_rows(db, org)

    with pytest.raises(HTTPException) as e:
        await delete_term(t.id, confirm=False, request=None, db=db, current_user=admin)

    assert e.value.status_code == 409
    detail = e.value.detail
    assert "PERMANENTLY DELETED" in detail
    assert "1 assessments" in detail and "1 scores" in detail
    # Nothing was destroyed by the refusal itself.
    assert (await db.execute(select(Assessment))).scalars().first() is not None
    assert (await db.execute(select(StudentAssessmentScore))).scalars().first() is not None


@pytest.mark.asyncio
async def test_the_warning_names_the_rows_that_merely_stop_matching(db, org):
    """The half the schema cannot see, and the half that caused the incident."""
    admin = await _admin(db, org)
    t = await _term_with_soft_rows(db, org)

    with pytest.raises(HTTPException) as e:
        await delete_term(t.id, confirm=False, request=None, db=db, current_user=admin)

    detail = e.value.detail
    assert "ORPHANED" in detail
    # Split the message, because a bare substring check passes whichever half the
    # row landed in — which is exactly how this test kept passing after migration
    # 131 moved report workflows from one half to the other.
    deleted, _, orphaned = detail.partition("LEFT ORPHANED")

    assert "1 CBT exams" in orphaned, (
        "term_id FK with ON DELETE SET NULL since migration 132 — the exam and its "
        "attempts survive, it is only detached, so it belongs in the orphaned half")
    assert "1 report workflows" in deleted, (
        "term_id FK with ON DELETE CASCADE since migration 131 — a delete DESTROYS "
        "the release, so warning that it is merely 'orphaned' would understate it")
    assert "1 report workflows" not in orphaned

    # And it must explain WHY orphaned rows matter, not just count them — for the
    # mechanism that actually applies. The old message claimed the CBT sync, the
    # freeze and the report-card gate "all match a term BY NAME"; migrations 131 and
    # 132 moved all three onto term_id, so that sentence would now mislead.
    assert "lose which term they belong to" in detail
    assert "BY NAME" not in detail, (
        "the CBT sync, the publish freeze and the report-card gate all key on "
        "term_id now — telling an admin to look for a spelling problem sends them "
        "after a cause that cannot exist")


@pytest.mark.asyncio
async def test_confirm_true_goes_through(db, org):
    """The guard informs; it does not forbid. An admin who has read the counts
    must still be able to proceed."""
    admin = await _admin(db, org)
    t, _, _ = await _term_with_hard_rows(db, org)

    await delete_term(t.id, confirm=True, request=None, db=db, current_user=admin)

    assert (await db.execute(select(AcademicTerm))).scalars().first() is None


# ── the record ────────────────────────────────────────────────────────────────

async def _audit(db, resource_type="AcademicTerm"):
    return (await db.execute(
        select(AuditLog).where(AuditLog.resource_type == resource_type)
    )).scalars().all()


@pytest.mark.asyncio
async def test_a_delete_is_recorded_with_what_it_destroyed(db, org):
    """There was no record of the September delete. Who, what, and how much."""
    admin = await _admin(db, org)
    t, _, _ = await _term_with_hard_rows(db, org)

    await delete_term(t.id, confirm=True, request=None, db=db, current_user=admin)

    rows = await _audit(db)
    assert len(rows) == 1, "a term delete must leave exactly one record"
    entry = rows[0]
    assert TERM in (entry.resource_label or "")
    assert entry.actor_id == admin.id
    assert entry.severity == "warning", "destroying marks is not routine-edit noise"
    # The counts ride along, so the record is useful without the deleted rows.
    assert (entry.new_values or {}).get("cascaded", {}).get("assessments") == 1


@pytest.mark.asyncio
async def test_creating_a_term_is_recorded(db, org):
    admin = await _admin(db, org)

    await create_term(TermCreate(name="Spring"), request=None, db=db, current_user=admin)

    rows = await _audit(db)
    assert len(rows) == 1 and "Spring" in (rows[0].resource_label or "")


@pytest.mark.asyncio
async def test_renaming_a_term_no_longer_strands_the_rows_that_hold_its_id(db, org):
    """This test used to assert that a rename stranded the CBT exam, because the exam
    stored the term's NAME and the rename left it pointing at a name nothing used.
    That WAS the incident, and migration 132 ended it: the exam holds term_id, so a
    rename moves the name underneath it and the link survives.

    So the rename is still recorded, but with nothing stranded and at info severity —
    a warning here would train an admin to ignore warnings."""
    admin = await _admin(db, org)
    t = await _term_with_soft_rows(db, org)

    await update_term(t.id, TermUpdate(name="Michaelmas"), request=None,
                      db=db, current_user=admin)

    rows = await _audit(db)
    assert len(rows) == 1
    entry = rows[0]
    assert "Autumn" in (entry.resource_label or "") and "Michaelmas" in (entry.resource_label or "")
    assert (entry.old_values or {}).get("name") == TERM
    stranded = (entry.new_values or {}).get("stranded") or {}
    assert stranded == {}, f"a rename strands nothing in this fixture now, got {stranded}"
    assert entry.severity == "info"

    # And the exam still points at the term it was sat in, under its new name.
    exam = (await db.execute(select(CBTExam))).scalars().first()
    assert exam.term_id == t.id


@pytest.mark.asyncio
async def test_an_unrelated_edit_is_not_logged_as_a_rename(db, org):
    """Only the name is the join key. Editing anything else must not raise a
    warning-level record, or the signal gets buried."""
    admin = await _admin(db, org)
    t = await _bare_term(db, org)

    await update_term(t.id, TermUpdate(is_active=True), request=None,
                      db=db, current_user=admin)

    assert await _audit(db) == []
