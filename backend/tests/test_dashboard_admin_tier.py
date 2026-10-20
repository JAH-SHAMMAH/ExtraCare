"""Who may see the whole-school headcounts / the Teachers menu — by real preset."""
import uuid

import pytest

from app.models.role import SCHOOL_PERMISSION_PRESETS as P, Role
from app.models.user import User, UserStatus
from app.routers.dashboard import _is_admin
from app.routers.me import contexts
from app.routers.modules.school import list_teachers  # noqa: F401  (import must keep working)

pytestmark = pytest.mark.asyncio


async def _user(db, org, slug):
    r = Role(id=str(uuid.uuid4()), name=slug, slug=slug, permissions=list(P[slug]), org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:5]}@x.com", full_name=slug,
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [r]
    db.add_all([r, u])
    await db.commit()
    return u


@pytest.mark.parametrize("slug", ["org_admin", "manager", "principal", "head", "vice_principal",
                                  "deputy_head", "head_of_administration", "hr_manager", "accountant"])
async def test_admin_tier_sees_headcounts(db, org, slug):
    assert _is_admin(await _user(db, org, slug)) is True


@pytest.mark.parametrize("slug", ["teacher", "instructor", "librarian", "janitor"])
async def test_staff_who_are_not_admin_do_not(db, org, slug):
    assert _is_admin(await _user(db, org, slug)) is False


@pytest.mark.parametrize("slug", ["principal", "head", "hr_manager", "accountant"])
async def test_these_roles_land_on_the_admin_home(db, org, slug):
    u = await _user(db, org, slug)
    from fastapi import Response
    res = await contexts(response=Response(), db=db, current_user=u)
    assert "admin" in res["available_roles"] and res["default_role"] == "admin"


async def test_teacher_is_not_given_the_admin_home(db, org):
    u = await _user(db, org, "teacher")
    from fastapi import Response
    res = await contexts(response=Response(), db=db, current_user=u)
    assert "admin" not in res["available_roles"]


@pytest.mark.parametrize("slug,expected", [
    ("principal", True), ("head", True), ("manager", True), ("hr_manager", True),
    # Teachers keep API read (Lesson Planner / Ratings use it); the MENU is hidden
    # from them by the frontend access map, tested in access.teachersMenu.test.ts.
    ("teacher", True), ("accountant", False),
])
async def test_teachers_list_scope(db, org, slug, expected):
    u = await _user(db, org, slug)
    ok = u.has_permission("school:teachers:read") or u.has_permission("hr:write")
    assert ok is expected
