"""Tests for Lesson Planner Setup — categories, settings, supervisors, clone.

Proves the setup surface behind the tabs:
  • category CRUD is tenant-scoped, a plan can carry a category, a foreign
    category_id is refused, and deleting a category detaches its plans (no dangle);
  • the settings singleton returns defaults then persists edits;
  • supervisor assignments add/list/remove; a foreign supervisor is refused;
  • clone copies plans preserving each plan's day-offset and skips an existing target.
"""
from __future__ import annotations

import uuid
from datetime import date, time, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import LessonPlan
from app.models.modules.platform import MailboxRecipient
from app.routers.modules.school import (
    create_lesson, update_lesson, list_lessons, publish_lesson,
    list_lesson_categories, create_lesson_category, update_lesson_category, delete_lesson_category,
    get_planner_settings, update_planner_settings,
    list_lesson_supervisors, add_lesson_supervisor, remove_lesson_supervisor,
    clone_lessons, create_subject,
    list_schedules, create_schedule, update_schedule, delete_schedule,
    send_schedule_now, run_due_schedules,
)
from app.schemas.lesson_planner import (
    CategoryCreate, CategoryUpdate, PlannerSettingsUpdate, SupervisorCreate, CloneLessonsRequest,
    ScheduleCreate, ScheduleUpdate,
)
from app.schemas.subject import SubjectCreate


async def _user_with_role(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@x.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=slug, permissions=[], org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _recipient_ids(db, org):
    return set((await db.execute(select(MailboxRecipient.recipient_id).where(MailboxRecipient.org_id == org.id))).scalars().all())


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    """An org_admin whose role.slug is EXACTLY 'org_admin' so _is_admin_role holds
    (the generic preset helper suffixes the slug, which would read as non-admin)."""
    u = User(id=str(uuid.uuid4()), email=f"admin-{uuid.uuid4().hex[:6]}@x.com",
             full_name="Admin User", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="org_admin", slug="org_admin",
                permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _subject(db, user, name="Mathematics"):
    return await create_subject(SubjectCreate(name=name), request=None, db=db, current_user=user)


async def _plan(db, user, class_id, subject_id, on: str, title="Lesson", **extra):
    payload = {"title": title, "class_id": class_id, "subject_id": subject_id, "lesson_date": on, **extra}
    return await create_lesson(payload=payload, request=None, db=db, current_user=user)


# ── Categories ────────────────────────────────────────────────────────────────

async def test_category_crud_link_and_delete_detaches(db, org, school_class):
    admin = await _admin(db, org)
    subj = await _subject(db, admin)

    cat = await create_lesson_category(CategoryCreate(name="Practical"), db=db, current_user=admin)
    assert cat["name"] == "Practical"
    renamed = await update_lesson_category(cat["id"], CategoryUpdate(name="Lab / Practical"), db=db, current_user=admin)
    assert renamed["name"] == "Lab / Practical"

    # A plan can carry the category; a foreign id is refused.
    plan = await _plan(db, admin, school_class.id, subj["id"], "2026-01-14", category_id=cat["id"])
    assert plan["category_id"] == cat["id"]
    with pytest.raises(HTTPException) as ei:
        await _plan(db, admin, school_class.id, subj["id"], "2026-01-15", category_id=str(uuid.uuid4()))
    assert ei.value.status_code == 422

    # Deleting the category detaches the plan (no dangling reference).
    await delete_lesson_category(cat["id"], db=db, current_user=admin)
    assert await list_lesson_categories(db=db, current_user=admin) == []
    row = (await db.execute(select(LessonPlan).where(LessonPlan.id == plan["id"]))).scalar_one()
    assert row.category_id is None


async def test_category_duplicate_name_conflicts(db, org):
    admin = await _admin(db, org)
    await create_lesson_category(CategoryCreate(name="Theory"), db=db, current_user=admin)
    with pytest.raises(HTTPException) as ei:
        await create_lesson_category(CategoryCreate(name="Theory"), db=db, current_user=admin)
    assert ei.value.status_code == 409


# ── Settings ──────────────────────────────────────────────────────────────────

async def test_settings_default_then_update(db, org):
    admin = await _admin(db, org)
    s = await get_planner_settings(db=db, current_user=admin)
    assert s["require_approval"] is False and s["default_duration_minutes"] == 45 and s["allow_backdated"] is True

    upd = await update_planner_settings(
        PlannerSettingsUpdate(require_approval=True, default_duration_minutes=60), db=db, current_user=admin)
    assert upd["require_approval"] is True and upd["default_duration_minutes"] == 60
    # Persisted (singleton reused, not duplicated).
    again = await get_planner_settings(db=db, current_user=admin)
    assert again["require_approval"] is True and again["allow_backdated"] is True


# ── Supervisors ───────────────────────────────────────────────────────────────

async def test_supervisor_add_list_remove_and_foreign_refused(db, org, teacher):
    admin = await _admin(db, org)
    row = await add_lesson_supervisor(SupervisorCreate(supervisor_id=teacher.id), db=db, current_user=admin)
    assert row["supervisor_id"] == teacher.id and row["section_id"] is None
    listed = await list_lesson_supervisors(db=db, current_user=admin)
    assert any(r["id"] == row["id"] and r["supervisor_name"] for r in listed)

    with pytest.raises(HTTPException) as ei:
        await add_lesson_supervisor(SupervisorCreate(supervisor_id=str(uuid.uuid4())), db=db, current_user=admin)
    assert ei.value.status_code == 422

    await remove_lesson_supervisor(row["id"], db=db, current_user=admin)
    assert await list_lesson_supervisors(db=db, current_user=admin) == []


# ── Clone ─────────────────────────────────────────────────────────────────────

async def test_clone_preserves_offset_and_skips_existing(db, org, school_class):
    admin = await _admin(db, org)
    subj = await _subject(db, admin)
    # Two source plans: Mon 12th (offset 0) + Wed 14th (offset +2).
    await _plan(db, admin, school_class.id, subj["id"], "2026-01-12", title="A", period=1)
    await _plan(db, admin, school_class.id, subj["id"], "2026-01-14", title="B", period=1)

    res = await clone_lessons(CloneLessonsRequest(
        source_start=date(2026, 1, 12), source_end=date(2026, 1, 18),
        target_start=date(2026, 1, 19)), db=db, current_user=admin)
    assert res["cloned"] == 2 and res["skipped"] == 0
    # Offsets preserved: 12→19 (Mon), 14→21 (Wed); all drafts.
    cloned = await list_lessons(start_date="2026-01-19", end_date="2026-01-25", db=db, current_user=admin)
    dates = {c["lesson_date"] for c in cloned["items"]}
    assert dates == {"2026-01-19", "2026-01-21"}
    assert all(c["status"] == "draft" for c in cloned["items"])

    # Re-cloning the same window skips both (target already populated).
    again = await clone_lessons(CloneLessonsRequest(
        source_start=date(2026, 1, 12), source_end=date(2026, 1, 18),
        target_start=date(2026, 1, 19)), db=db, current_user=admin)
    assert again["cloned"] == 0 and again["skipped"] == 2


# ── Settings enforcement (opt-in; defaults keep current behaviour) ─────────────────

async def test_require_approval_forces_draft_and_gates_teacher_publish(db, org, school_class, teacher):
    admin = await _admin(db, org)
    subj = await _subject(db, admin)
    await update_planner_settings(PlannerSettingsUpdate(require_approval=True), db=db, current_user=admin)

    # A teacher's "publish" create is forced to draft…
    plan = await _plan(db, teacher, school_class.id, subj["id"], "2026-09-14", title="T", status="published")
    assert plan["status"] == "draft"
    # …and the teacher cannot self-publish it.
    with pytest.raises(HTTPException) as ei:
        await publish_lesson(plan["id"], request=None, db=db, current_user=teacher)
    assert ei.value.status_code == 403
    # A supervisor/admin publishes = approves.
    pub = await publish_lesson(plan["id"], request=None, db=db, current_user=admin)
    assert pub["status"] == "published"


async def test_allow_backdated_false_rejects_past_for_teacher_only(db, org, school_class, teacher):
    admin = await _admin(db, org)
    subj = await _subject(db, admin)
    await update_planner_settings(PlannerSettingsUpdate(allow_backdated=False), db=db, current_user=admin)

    with pytest.raises(HTTPException) as ei:
        await _plan(db, teacher, school_class.id, subj["id"], "2020-01-01", title="Past")
    assert ei.value.status_code == 422
    # Admin bypasses the rule; a future date is fine for the teacher.
    assert (await _plan(db, admin, school_class.id, subj["id"], "2020-01-01", title="AdminPast"))["status"] == "draft"
    assert (await _plan(db, teacher, school_class.id, subj["id"], "2027-01-01", title="Future"))["status"] == "draft"


async def test_default_duration_from_settings(db, org, school_class):
    admin = await _admin(db, org)
    subj = await _subject(db, admin)
    await update_planner_settings(PlannerSettingsUpdate(default_duration_minutes=60), db=db, current_user=admin)
    plan = await _plan(db, admin, school_class.id, subj["id"], "2027-02-01", title="D")  # no duration passed
    assert plan["duration_minutes"] == 60


# ── Reminder schedules ────────────────────────────────────────────────────────────

async def test_schedule_crud_and_weekly_requires_days(db, org):
    admin = await _admin(db, org)
    # Weekly with no days is rejected.
    with pytest.raises(HTTPException) as ei:
        await create_schedule(ScheduleCreate(subject="Submit plans", frequency="weekly", days=[], run_time=time(8, 0)), db=db, current_user=admin)
    assert ei.value.status_code == 422

    s = await create_schedule(ScheduleCreate(subject="Submit plans", frequency="weekly", days=[4, 0, 4], run_time=time(8, 0)), db=db, current_user=admin)
    assert s["days"] == [0, 4] and s["is_active"] is True   # deduped + sorted
    listed = await list_schedules(db=db, current_user=admin)
    assert any(x["id"] == s["id"] for x in listed)

    upd = await update_schedule(s["id"], ScheduleUpdate(is_active=False, subject="Reminder"), db=db, current_user=admin)
    assert upd["is_active"] is False and upd["subject"] == "Reminder"

    await delete_schedule(s["id"], db=db, current_user=admin)
    assert await list_schedules(db=db, current_user=admin) == []


async def test_send_now_targets_teaching_staff_not_students(db, org):
    admin = await _admin(db, org)              # sender (excluded from recipients)
    teacher = await _user_with_role(db, org, "teacher")
    student = await _user_with_role(db, org, "student")

    s = await create_schedule(ScheduleCreate(subject="Plans due Friday", audience="teachers", frequency="daily", run_time=time(7, 0)), db=db, current_user=admin)
    res = await send_schedule_now(s["id"], db=db, current_user=admin)
    recips = await _recipient_ids(db, org)
    # Teaching-staff audience reaches the teacher, never the student, never the sender.
    assert teacher.id in recips and student.id not in recips and admin.id not in recips
    assert res["dispatched"] == 1 and res["recipients"] == len(recips)


async def test_all_staff_audience_includes_students(db, org):
    admin = await _admin(db, org)
    teacher = await _user_with_role(db, org, "teacher")
    student = await _user_with_role(db, org, "student")
    s = await create_schedule(ScheduleCreate(subject="Notice", audience="all_staff", frequency="daily", run_time=time(0, 0)), db=db, current_user=admin)
    await send_schedule_now(s["id"], db=db, current_user=admin)
    recips = await _recipient_ids(db, org)
    assert {teacher.id, student.id} <= recips


async def test_run_due_fires_only_due_and_is_idempotent(db, org):
    admin = await _admin(db, org)
    await _user_with_role(db, org, "teacher")
    today = datetime.now().weekday()
    # Due now: daily, time already passed today.
    due = await create_schedule(ScheduleCreate(subject="Due", frequency="daily", run_time=time(0, 0)), db=db, current_user=admin)
    # Not due: weekly on a different weekday.
    await create_schedule(ScheduleCreate(subject="Other day", frequency="weekly", days=[(today + 1) % 7], run_time=time(0, 0)), db=db, current_user=admin)
    # Not due: time-of-day still in the future.
    await create_schedule(ScheduleCreate(subject="Later", frequency="daily", run_time=time(23, 59)), db=db, current_user=admin)

    first = await run_due_schedules(db=db, current_user=admin)
    assert first["dispatched"] == 1 and first["recipients"] >= 1
    # Idempotent: the due one already ran today → nothing fires again.
    second = await run_due_schedules(db=db, current_user=admin)
    assert second["dispatched"] == 0
    fetched = next(x for x in await list_schedules(db=db, current_user=admin) if x["id"] == due["id"])
    assert fetched["last_run_on"] == date.today()


# ── Educare settings fields + "Edit Lesson Plan" lock ─────────────────────────

async def test_planner_settings_educare_fields(db, org):
    admin = await _admin(db, org)
    s = await get_planner_settings(db=db, current_user=admin)
    # New Educare fields present with sensible defaults.
    assert s["display_category_names"] is True and s["change_subject_topic"] is False
    assert s["change_day_format"] is False and s["edit_lesson_plan"] is False and s["supervisor_signature"] is None

    upd = await update_planner_settings(
        PlannerSettingsUpdate(display_category_names=False, change_subject_topic=True, change_day_format=True,
                              edit_lesson_plan=True, supervisor_signature="/uploads/o/documents/sig.png"),
        db=db, current_user=admin,
    )
    assert upd["display_category_names"] is False and upd["change_subject_topic"] is True
    assert upd["change_day_format"] is True and upd["edit_lesson_plan"] is True
    assert upd["supervisor_signature"].endswith("sig.png")


async def test_edit_lesson_plan_locks_published(db, org, school_class):
    admin = await _admin(db, org)
    subj = await _subject(db, admin)
    plan = await _plan(db, admin, school_class.id, subj["id"], "2026-02-10")
    await publish_lesson(plan["id"], request=None, db=db, current_user=admin)   # now published

    # edit_lesson_plan defaults False → editing a published plan's CONTENT is refused.
    with pytest.raises(HTTPException) as exc:
        await update_lesson(plan["id"], payload={"title": "Changed"}, request=None, db=db, current_user=admin)
    assert exc.value.status_code == 409

    # Status-only change (unpublish) is still allowed.
    unp = await update_lesson(plan["id"], payload={"status": "draft"}, request=None, db=db, current_user=admin)
    assert unp["status"] == "draft"

    # Enable the setting → content edits on a published plan now work.
    await update_planner_settings(PlannerSettingsUpdate(edit_lesson_plan=True), db=db, current_user=admin)
    await publish_lesson(plan["id"], request=None, db=db, current_user=admin)
    ok = await update_lesson(plan["id"], payload={"title": "Now Editable"}, request=None, db=db, current_user=admin)
    assert ok["title"] == "Now Editable"
