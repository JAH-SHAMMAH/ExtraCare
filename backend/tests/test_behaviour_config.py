"""Behaviour Tracker admin: category/sub-category taxonomy, conduct-level bands,
settings, and point-based level classification. All staff-gated (school:behaviour).
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import (
    Student, BehaviourRecord, BehaviourType,
    BehaviourCategory, BehaviourSubCategory,
)
from app.schemas.behaviour_config import (
    CategoryCreate, CategoryUpdate, SubCategoryCreate, LevelCreate, LevelUpdate, SettingsUpdate,
)
from app.schemas.school_experience import BehaviourCreate
from app.routers.modules.behaviour import (
    list_categories, create_category, update_category, delete_category,
    list_subcategories, create_subcategory, delete_subcategory,
    list_levels, create_level, update_level,
    get_settings, update_settings, student_summary, create_record,
)

pytestmark = pytest.mark.asyncio


async def _staff(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"staff-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Staff", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="manager", slug=f"m-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["manager"]), org_id=org.id, is_system=False)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _second_org(db) -> Organization:
    o = Organization(id=str(uuid.uuid4()), name="Other School", slug=f"other-{uuid.uuid4().hex[:8]}",
                     industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(o)
    await db.commit()
    return o


async def _student(db, org) -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
                first_name="S", last_name="X", org_id=org.id)
    db.add(s)
    await db.commit()
    return s


# ── Categories + sub-categories ──────────────────────────────────────────────

async def test_category_crud(db, org):
    staff = await _staff(db, org)
    cat = await create_category(CategoryCreate(name="Punctuality", type="negative", default_points=-2),
                                request=None, db=db, current_user=staff)
    assert cat["name"] == "Punctuality" and cat["default_points"] == -2

    listed = await list_categories(db=db, current_user=staff)
    assert len(listed["items"]) == 1

    upd = await update_category(cat["id"], CategoryUpdate(name="Timekeeping", is_active=False),
                                request=None, db=db, current_user=staff)
    assert upd["name"] == "Timekeeping" and upd["is_active"] is False

    await delete_category(cat["id"], request=None, db=db, current_user=staff)
    assert (await list_categories(db=db, current_user=staff))["items"] == []


async def test_subcategory_requires_parent_and_delete_guard(db, org):
    staff = await _staff(db, org)
    cat = await create_category(CategoryCreate(name="Punctuality"), request=None, db=db, current_user=staff)
    sub = await create_subcategory(SubCategoryCreate(category_id=cat["id"], name="Late to class"),
                                   request=None, db=db, current_user=staff)
    assert sub["category_id"] == cat["id"]
    # filter by parent
    listed = await list_subcategories(category_id=cat["id"], db=db, current_user=staff)
    assert len(listed["items"]) == 1

    # deleting a category with a sub-category is blocked (409)
    with pytest.raises(Exception) as ei:
        await delete_category(cat["id"], request=None, db=db, current_user=staff)
    assert getattr(ei.value, "status_code", None) == 409

    # unknown parent → 404
    with pytest.raises(Exception) as ei2:
        await create_subcategory(SubCategoryCreate(category_id="nope", name="x"),
                                 request=None, db=db, current_user=staff)
    assert getattr(ei2.value, "status_code", None) == 404


async def test_category_delete_blocked_when_referenced_by_record(db, org):
    staff = await _staff(db, org)
    stu = await _student(db, org)
    cat = await create_category(CategoryCreate(name="Teamwork", type="positive"),
                                request=None, db=db, current_user=staff)
    db.add(BehaviourRecord(id=str(uuid.uuid4()), student_id=stu.id, recorded_by=staff.id,
                           type=BehaviourType.POSITIVE, category_id=cat["id"], description="Helped a peer",
                           points=3, incident_date=date.today(), org_id=org.id))
    await db.commit()
    with pytest.raises(Exception) as ei:
        await delete_category(cat["id"], request=None, db=db, current_user=staff)
    assert getattr(ei.value, "status_code", None) == 409


# ── Levels + classification ──────────────────────────────────────────────────

async def test_level_validation_and_crud(db, org):
    staff = await _staff(db, org)
    with pytest.raises(Exception) as ei:
        await create_level(LevelCreate(name="Bad", min_points=10, max_points=5),
                           request=None, db=db, current_user=staff)
    assert getattr(ei.value, "status_code", None) == 422

    lv = await create_level(LevelCreate(name="Good", min_points=10, max_points=19),
                            request=None, db=db, current_user=staff)
    assert lv["min_points"] == 10
    with pytest.raises(Exception):
        await update_level(lv["id"], LevelUpdate(max_points=3), request=None, db=db, current_user=staff)


async def test_student_level_classification_from_points(db, org):
    staff = await _staff(db, org)
    stu = await _student(db, org)
    # bands: Concern <0, Fair 0-9, Good 10-19, Excellent >=20 (open top)
    for name, lo, hi in [("Concern", -100, -1), ("Fair", 0, 9), ("Good", 10, 19), ("Excellent", 20, None)]:
        await create_level(LevelCreate(name=name, min_points=lo, max_points=hi),
                           request=None, db=db, current_user=staff)
    # +15 net points → "Good"
    db.add_all([
        BehaviourRecord(id=str(uuid.uuid4()), student_id=stu.id, recorded_by=staff.id,
                        type=BehaviourType.POSITIVE, description="a", points=20,
                        incident_date=date.today(), org_id=org.id),
        BehaviourRecord(id=str(uuid.uuid4()), student_id=stu.id, recorded_by=staff.id,
                        type=BehaviourType.NEGATIVE, description="b", points=-5,
                        incident_date=date.today(), org_id=org.id),
    ])
    await db.commit()

    summary = await student_summary(stu.id, db=db, current_user=staff)
    assert summary["total_points"] == 15
    assert summary["level"]["name"] == "Good"

    # turning auto-derivation off suppresses the level
    await update_settings(SettingsUpdate(auto_derive_levels=False), request=None, db=db, current_user=staff)
    summary2 = await student_summary(stu.id, db=db, current_user=staff)
    assert summary2["level"] is None


# ── Record taxonomy validation (tenant safety) ───────────────────────────────

async def test_record_validates_taxonomy_ownership(db, org):
    staff = await _staff(db, org)
    stu = await _student(db, org)
    cat = await create_category(CategoryCreate(name="Punctuality"), request=None, db=db, current_user=staff)
    sub = await create_subcategory(SubCategoryCreate(category_id=cat["id"], name="Late"),
                                   request=None, db=db, current_user=staff)

    # a category id that isn't in this tenant → 404
    with pytest.raises(Exception) as ei:
        await create_record(BehaviourCreate(student_id=stu.id, description="x", incident_date=date.today(),
                                            category_id="nope"), request=None, db=db, current_user=staff)
    assert getattr(ei.value, "status_code", None) == 404

    # a sub-category that doesn't sit under the chosen category → 422
    cat2 = await create_category(CategoryCreate(name="Teamwork"), request=None, db=db, current_user=staff)
    with pytest.raises(Exception) as ei2:
        await create_record(BehaviourCreate(student_id=stu.id, description="x", incident_date=date.today(),
                                            category_id=cat2["id"], subcategory_id=sub["id"]),
                            request=None, db=db, current_user=staff)
    assert getattr(ei2.value, "status_code", None) == 422

    # a category from another org → 404 (cross-tenant)
    other = await _second_org(db)
    other_staff = await _staff(db, other)
    foreign = await create_category(CategoryCreate(name="Foreign"), request=None, db=db, current_user=other_staff)
    with pytest.raises(Exception) as ei3:
        await create_record(BehaviourCreate(student_id=stu.id, description="x", incident_date=date.today(),
                                            category_id=foreign["id"]), request=None, db=db, current_user=staff)
    assert getattr(ei3.value, "status_code", None) == 404

    # valid combo → record created with the refs
    rec = await create_record(BehaviourCreate(student_id=stu.id, description="Helped", incident_date=date.today(),
                                              category_id=cat["id"], subcategory_id=sub["id"], points=2),
                              request=None, db=db, current_user=staff)
    assert rec["category_id"] == cat["id"] and rec["subcategory_id"] == sub["id"]


# ── Settings ─────────────────────────────────────────────────────────────────

async def test_settings_get_or_create_and_update(db, org):
    staff = await _staff(db, org)
    s = await get_settings(db=db, current_user=staff)  # auto-created with defaults
    assert s["default_points"] == 1 and s["auto_derive_levels"] is True
    upd = await update_settings(SettingsUpdate(default_points=5, visible_to_parents=True),
                                request=None, db=db, current_user=staff)
    assert upd["default_points"] == 5 and upd["visible_to_parents"] is True


# ── Tenant scoping + RBAC ────────────────────────────────────────────────────

async def test_categories_are_tenant_scoped(db, org):
    staff = await _staff(db, org)
    await create_category(CategoryCreate(name="OrgA cat"), request=None, db=db, current_user=staff)
    other = await _second_org(db)
    other_staff = await _staff(db, other)
    assert (await list_categories(db=db, current_user=other_staff))["items"] == []


async def test_behaviour_config_is_staff_write_only(db, org):
    staff = await _staff(db, org)
    assert staff.has_permission("school:behaviour:write")
    stu_role = Role(id=str(uuid.uuid4()), name="student", slug=f"stu-{uuid.uuid4().hex[:6]}",
                    permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    stu_user = User(id=str(uuid.uuid4()), email=f"s-{uuid.uuid4().hex[:6]}@example.com",
                    full_name="Stu", status=UserStatus.ACTIVE, org_id=org.id)
    stu_user.roles = [stu_role]
    db.add_all([stu_role, stu_user])
    await db.commit()
    assert not stu_user.has_permission("school:behaviour:write")
