"""Tests for migration 125's ReportApproval backfill planner.

The migration re-states an existing fact — "these classes' results are already in
front of parents" — in the vocabulary the new report-card gate reads. Get the
scope wrong in either direction and it is production-visible: too narrow and live
cards go blank, too wide and it releases a class nobody released.

So the planner is tested here, not only dry-run against production:
  • one row per (class, term) that HAS published grades, and nothing else
  • draft-only classes are not touched
  • pairs that already hold a row are left exactly as they are (idempotent)
  • published grades that can't be gated (no class, no term) are reported by
    their absence rather than silently invented
  • and the end-to-end point: after the backfill, a parent who could see a card
    before the gate shipped can still see it.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Grade, GradeStatus, Student, SchoolClass, ParentGuardian, Subject
from app.models.modules.academics import ReportApproval
from app.routers.modules.school import get_report_card
from app.services.report_approval_backfill import BACKFILL_NOTE, apply_backfill, plan_backfill

pytestmark = pytest.mark.asyncio


async def _plan(db):
    """plan_backfill against the test session's connection (it takes the sync
    connection Alembic would hand it)."""
    return await db.run_sync(lambda s: plan_backfill(s.connection()))


async def _apply(db, rows):
    written = await db.run_sync(lambda s: apply_backfill(s.connection(), rows))
    await db.commit()
    return written


async def _class(db, org, name) -> SchoolClass:
    c = SchoolClass(id=str(uuid.uuid4()), name=name, level="Secondary",
                    academic_year="2025/2026", org_id=org.id)
    db.add(c)
    await db.commit()
    return c


async def _student_with_grade(db, org, cls, *, term="Term 1", status=GradeStatus.PUBLISHED,
                              subject_id=None, email=None) -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
                first_name="A", last_name="B", email=email,
                class_id=cls.id if cls else None, org_id=org.id)
    db.add(s)
    if subject_id is None:
        subj = Subject(id=str(uuid.uuid4()), name=f"Subj-{uuid.uuid4().hex[:4]}", org_id=org.id)
        db.add(subj)
        subject_id = subj.id
    db.add(Grade(id=str(uuid.uuid4()), student_id=s.id, subject_id=subject_id, score=80,
                 max_score=100, term=term, status=status, org_id=org.id))
    await db.commit()
    return s


async def test_plan_covers_exactly_the_published_pairs(db, org):
    published = await _class(db, org, "JSS1 A")
    drafted = await _class(db, org, "JSS1 B")
    await _student_with_grade(db, org, published, term="Term 1")
    await _student_with_grade(db, org, published, term="Term 1")   # same pair, one row
    await _student_with_grade(db, org, published, term="Term 2")   # distinct pair
    await _student_with_grade(db, org, drafted, status=GradeStatus.DRAFT)

    to_create, skipped = await _plan(db)

    assert skipped == []
    pairs = {(r["class_name"], r["term"]) for r in to_create}
    assert pairs == {("JSS1 A", "Term 1"), ("JSS1 A", "Term 2")}
    assert all(r["stage"] == "published" for r in to_create)
    assert all(r["academic_year"] is None for r in to_create)  # no current session seeded here
    term1 = next(r for r in to_create if r["term"] == "Term 1")
    assert term1["grade_rows"] == 2 and term1["students"] == 2


async def test_plan_ignores_grades_it_cannot_gate(db, org):
    """A published grade with no class or no term has nothing to key a workflow
    row on. It is left out rather than guessed at — visible in the dry-run as an
    orphan count, not papered over here."""
    cls = await _class(db, org, "JSS2 A")
    await _student_with_grade(db, org, None, term="Term 1")      # no class
    await _student_with_grade(db, org, cls, term=None)           # no term

    to_create, _ = await _plan(db)
    assert to_create == []


async def test_existing_rows_are_left_alone(db, org):
    """A pair already holding a row is reported, not overwritten — including one
    parked below `published`, which the operator needs to see because its cards
    stay hidden."""
    cls = await _class(db, org, "SSS1 A")
    await _student_with_grade(db, org, cls)
    db.add(ReportApproval(id=str(uuid.uuid4()), class_id=cls.id, term="Term 1",
                          stage="reviewed", notes="hand-made", org_id=org.id))
    await db.commit()

    to_create, skipped = await _plan(db)
    assert to_create == []
    assert len(skipped) == 1
    assert skipped[0]["existing_stage"] == "reviewed"
    assert skipped[0]["class_name"] == "SSS1 A"

    row = (await db.execute(select(ReportApproval))).scalar_one()
    assert row.stage == "reviewed" and row.notes == "hand-made"  # untouched


async def test_backfill_is_idempotent(db, org):
    cls = await _class(db, org, "SSS2 A")
    await _student_with_grade(db, org, cls)

    first, _ = await _plan(db)
    assert await _apply(db, first) == 1

    second, skipped = await _plan(db)
    assert second == [] and len(skipped) == 1
    assert await _apply(db, second) == 0
    assert len((await db.execute(select(ReportApproval))).scalars().all()) == 1


async def test_applied_rows_carry_the_publish_stamp(db, org):
    cls = await _class(db, org, "SSS3 A")
    await _student_with_grade(db, org, cls)
    to_create, _ = await _plan(db)
    await _apply(db, to_create)

    row = (await db.execute(select(ReportApproval))).scalar_one()
    assert row.stage == "published"
    assert row.published_at is not None
    assert row.published_by is None      # a migration has no actor to credit
    assert row.notes == BACKFILL_NOTE    # and downgrade() finds it by this marker


async def test_backfill_restores_parent_visibility(db, org):
    """The whole point, end to end: a card a parent could see before the gate
    shipped is visible again after the backfill, and only because of it."""
    cls = await _class(db, org, "JSS3 A")
    parent = User(id=str(uuid.uuid4()), email=f"p-{uuid.uuid4().hex[:6]}@example.com",
                  full_name="Parent", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="parent", slug=f"parent-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["parent"]), org_id=org.id, is_system=False)
    parent.roles = [role]
    db.add_all([role, parent])
    child = await _student_with_grade(db, org, cls, term="Term 1")
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=child.id, org_id=org.id))
    await db.commit()

    # Pre-migration world: grades published, no workflow row -> the new gate hides them.
    blank = await get_report_card(child.id, term="Term 1", db=db, current_user=parent)
    assert blank["grades"] == []

    to_create, _ = await _plan(db)
    await _apply(db, to_create)

    restored = await get_report_card(child.id, term="Term 1", db=db, current_user=parent)
    assert len(restored["grades"]) == 1 and restored["grades"][0]["score"] == 80


async def test_backfill_does_not_release_a_draft_class(db, org):
    """A class whose grades are still draft gets no row — the backfill re-states
    what is already visible, it does not publish anything new."""
    cls = await _class(db, org, "Year 6 A")
    await _student_with_grade(db, org, cls, status=GradeStatus.DRAFT)

    to_create, _ = await _plan(db)
    await _apply(db, to_create)
    assert (await db.execute(select(ReportApproval))).scalars().all() == []
