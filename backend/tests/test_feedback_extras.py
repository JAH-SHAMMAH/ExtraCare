"""Feedback section extras: settings, staff daily reports, student daily reports,
and the light CRM pipeline. All staff-gated; per-student reports validate the
student belongs to the org; CRM stage is validated. Handlers called directly.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Student
from app.schemas.feedback_extras import (
    FeedbackSettingsUpdate, DailyReportCreate, StudentDailyReportCreate, CRMContactCreate, CRMContactUpdate,
)
from app.routers.modules.feedback import (
    get_feedback_settings, update_feedback_settings,
    list_daily_reports, create_daily_report, delete_daily_report,
    list_student_daily_reports, create_student_daily_report,
    list_crm, create_crm, update_crm,
)

pytestmark = pytest.mark.asyncio


async def _staff(db, org, slug="manager") -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _student(db, org) -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
                first_name="S", last_name="X", org_id=org.id)
    db.add(s)
    await db.commit()
    return s


# ── Settings ─────────────────────────────────────────────────────────────────

async def test_feedback_settings_get_or_create_and_update(db, org):
    staff = await _staff(db, org)
    s = await get_feedback_settings(db=db, current_user=staff)
    assert s["allow_anonymous"] is True and s["notify_on_submit"] is False
    upd = await update_feedback_settings(FeedbackSettingsUpdate(allow_anonymous=False, acknowledgement_message="Thanks!"),
                                         request=None, db=db, current_user=staff)
    assert upd["allow_anonymous"] is False and upd["acknowledgement_message"] == "Thanks!"


# ── Daily reports ─────────────────────────────────────────────────────────────

async def test_daily_report_crud_and_mine(db, org):
    staff = await _staff(db, org)
    r = await create_daily_report(DailyReportCreate(report_date=date.today(), summary="Taught algebra", highlights="Good engagement"),
                                  request=None, db=db, current_user=staff)
    assert r["summary"] == "Taught algebra" and r["author_id"] == staff.id and r["author_name"] == staff.full_name

    mine = await list_daily_reports(mine=True, author_id=None, db=db, current_user=staff)
    assert len(mine["items"]) == 1

    await delete_daily_report(r["id"], request=None, db=db, current_user=staff)
    assert (await list_daily_reports(mine=True, author_id=None, db=db, current_user=staff))["items"] == []


# ── Student daily reports ─────────────────────────────────────────────────────

async def test_student_daily_report_validates_student(db, org):
    staff = await _staff(db, org)
    stu = await _student(db, org)
    r = await create_student_daily_report(
        StudentDailyReportCreate(student_id=stu.id, report_date=date.today(), mood="happy", academic="On track"),
        request=None, db=db, current_user=staff)
    assert r["student_id"] == stu.id and r["student_name"] == "S X" and r["mood"] == "happy"
    assert len((await list_student_daily_reports(student_id=stu.id, db=db, current_user=staff))["items"]) == 1

    with pytest.raises(HTTPException) as ei:
        await create_student_daily_report(
            StudentDailyReportCreate(student_id="nope", report_date=date.today()),
            request=None, db=db, current_user=staff)
    assert ei.value.status_code == 404


async def test_student_daily_report_rejects_foreign_student(db, org):
    staff = await _staff(db, org)
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    await db.commit()
    foreign_student = await _student(db, other)
    with pytest.raises(HTTPException) as ei:
        await create_student_daily_report(
            StudentDailyReportCreate(student_id=foreign_student.id, report_date=date.today()),
            request=None, db=db, current_user=staff)
    assert ei.value.status_code == 404


# ── CRM ───────────────────────────────────────────────────────────────────────

async def test_crm_crud_and_stage_validation(db, org):
    staff = await _staff(db, org)
    c = await create_crm(CRMContactCreate(name="Jane Doe", email="jane@x.com", stage="new"),
                         request=None, db=db, current_user=staff)
    assert c["name"] == "Jane Doe" and c["stage"] == "new" and c["assigned_to"] == staff.id

    moved = await update_crm(c["id"], CRMContactUpdate(stage="engaged"), request=None, db=db, current_user=staff)
    assert moved["stage"] == "engaged"

    with pytest.raises(HTTPException) as ei:
        await create_crm(CRMContactCreate(name="Bad", stage="banana"), request=None, db=db, current_user=staff)
    assert ei.value.status_code == 422

    listed = await list_crm(stage="engaged", db=db, current_user=staff)
    assert len(listed["items"]) == 1


async def test_crm_is_tenant_scoped(db, org):
    staff = await _staff(db, org)
    await create_crm(CRMContactCreate(name="OrgA lead"), request=None, db=db, current_user=staff)
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    await db.commit()
    other_staff = await _staff(db, other)
    assert (await list_crm(stage=None, db=db, current_user=other_staff))["items"] == []
