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
    FeedbackSettingsUpdate, DailyReportCreate, DailyReportUpdate, StudentDailyReportCreate,
)
from app.routers.modules.feedback import (
    get_feedback_settings, update_feedback_settings,
    list_daily_reports, create_daily_report, update_daily_report, delete_daily_report,
    list_student_daily_reports, create_student_daily_report, list_student_daily_reports_for_student,
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


async def _linked_student(db, org):
    """A Student + a student-role User sharing an email, so _user_owns_student links them."""
    email = f"stu-{uuid.uuid4().hex[:6]}@example.com"
    stu = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
                  first_name="Kid", last_name="One", email=email, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="student", slug=f"student-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=email, full_name="Kid One", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([stu, role, u])
    await db.commit()
    return stu, u


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


# ── Daily report is author-only for edit/delete (admin override) ──────────────

async def test_daily_report_edit_delete_author_only(db, org):
    author = await _staff(db, org)
    other = await _staff(db, org)             # a different staff member (no settings:write)
    admin = await _staff(db, org, "org_admin")  # holds settings:write
    r = await create_daily_report(DailyReportCreate(report_date=date.today(), summary="Mine"),
                                  request=None, db=db, current_user=author)

    with pytest.raises(HTTPException) as ei:
        await update_daily_report(r["id"], DailyReportUpdate(summary="hijacked"), request=None, db=db, current_user=other)
    assert ei.value.status_code == 403

    # the author can edit; an admin (settings:write) can override
    ok = await update_daily_report(r["id"], DailyReportUpdate(summary="edited"), request=None, db=db, current_user=author)
    assert ok["summary"] == "edited"
    await delete_daily_report(r["id"], request=None, db=db, current_user=admin)  # admin override, no raise


# ── Student daily report: parent/owner read (ownership-scoped) ────────────────

async def test_student_daily_report_owner_read_scoped(db, org):
    staff = await _staff(db, org)
    stu, stu_user = await _linked_student(db, org)
    _, other_user = await _linked_student(db, org)
    await create_student_daily_report(
        StudentDailyReportCreate(student_id=stu.id, report_date=date.today(), academic="Great day"),
        request=None, db=db, current_user=staff)

    # the linked student (owner) sees their own reports
    own = await list_student_daily_reports_for_student(stu.id, db=db, current_user=stu_user)
    assert len(own["items"]) == 1 and own["items"][0]["academic"] == "Great day"
    # a different student can't read this student's reports
    with pytest.raises(HTTPException) as ei:
        await list_student_daily_reports_for_student(stu.id, db=db, current_user=other_user)
    assert ei.value.status_code == 403
    # staff (students:read) can read any student's reports
    assert len((await list_student_daily_reports_for_student(stu.id, db=db, current_user=staff))["items"]) == 1
