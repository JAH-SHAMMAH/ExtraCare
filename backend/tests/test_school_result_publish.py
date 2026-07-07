"""Tests for Result Publishing — the draft/published gate on grades.

Proves the correctness fix (drafts must not leak to parents/students) plus the
bulk publish workflow:
  • report-card shows staff everything, but shows an owner (parent/student) only
    published grades — drafts are hidden
  • publish_grades flips status for a class+term and reports the count
  • publish-status summarises published vs draft
  • publishing refuses a scope with no class or exam (too broad)
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Grade, GradeStatus, Student, ParentGuardian
from app.routers.modules.school import (
    get_report_card, publish_grades, grade_publish_status, create_subject,
)
from app.schemas.grade import GradePublish
from app.schemas.subject import SubjectCreate

pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _two_grades(db, org, teacher, student):
    """One draft + one published grade for the student, Term 1."""
    subj = await create_subject(SubjectCreate(name="Mathematics"), request=None, db=db, current_user=teacher)
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=80,
                 max_score=100, term="Term 1", status=GradeStatus.DRAFT, org_id=org.id))
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=90,
                 max_score=100, term="Term 1", status=GradeStatus.PUBLISHED, org_id=org.id))
    await db.commit()
    return subj


async def test_report_card_staff_sees_drafts(db, org, teacher, school_class, student):
    await _two_grades(db, org, teacher, student)
    staff = await _preset_user(db, org, "teacher")  # holds school:students:read
    card = await get_report_card(student.id, term="Term 1", db=db, current_user=staff)
    assert len(card["grades"]) == 2  # draft + published


async def test_report_card_owner_sees_published_only(db, org, teacher, school_class, student):
    await _two_grades(db, org, teacher, student)
    parent = await _preset_user(db, org, "parent")  # no school:students:read
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=student.id, org_id=org.id))
    await db.commit()
    card = await get_report_card(student.id, term="Term 1", db=db, current_user=parent)
    assert len(card["grades"]) == 1
    assert card["grades"][0]["score"] == 90 and card["grades"][0]["status"] == "published"
    assert card["average"] == 90


async def test_publish_flips_status_and_counts(db, org, teacher, school_class, student):
    subj = await create_subject(SubjectCreate(name="English"), request=None, db=db, current_user=teacher)
    g = Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=subj["id"], score=75,
              max_score=100, term="Term 1", status=GradeStatus.DRAFT, org_id=org.id)
    db.add(g)
    await db.commit()

    before = await grade_publish_status(term="Term 1", class_id=school_class.id, db=db, current_user=teacher)
    assert before["total"] == 1 and before["draft"] == 1 and before["published"] == 0

    res = await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="published"),
                               request=None, db=db, current_user=teacher)
    assert res["updated"] == 1 and res["status"] == "published"
    await db.refresh(g)
    assert g.status == GradeStatus.PUBLISHED

    after = await grade_publish_status(term="Term 1", class_id=school_class.id, db=db, current_user=teacher)
    assert after["published"] == 1 and after["draft"] == 0

    # unpublish round-trips
    await publish_grades(GradePublish(term="Term 1", class_id=school_class.id, status="draft"),
                         request=None, db=db, current_user=teacher)
    await db.refresh(g)
    assert g.status == GradeStatus.DRAFT


async def test_publish_refuses_broad_scope(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await publish_grades(GradePublish(term="Term 1", status="published"),
                             request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422
