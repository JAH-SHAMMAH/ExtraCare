"""A teacher must not read admin business, over real HTTP (route checks run)."""
from __future__ import annotations
import pytest
from tests.test_result_flow_e2e import world, http, _h, API  # noqa: F401

pytestmark = pytest.mark.asyncio


async def _exact(db, w):
    for u, slug in ((w["teacher"], "teacher"), (w["admin"], "org_admin")):
        for r in u.roles:
            r.slug = slug
    await db.commit()


@pytest.mark.parametrize("path", [
    "/hr/overview", "/hr/events", "/pastoral/points-analysis", "/pastoral/mentor-reports",
])
async def test_teacher_is_refused_admin_pages(http, db, org, world, path):
    await _exact(db, world)
    assert (await http.get(f"{API}{path}", headers=_h(world["teacher"]))).status_code == 403, path
    assert (await http.get(f"{API}{path}", headers=_h(world["admin"]))).status_code == 200, path


async def test_staff_directory_hides_security_fields_from_teachers(http, db, org, world):
    await _exact(db, world)
    world["admin"].phone = "08000000000"
    await db.commit()
    t = (await http.get(f"{API}/users/staff", headers=_h(world["teacher"]))).json()
    assert t and all(u["phone"] is None and u["last_login_ip"] is None for u in t)
    a = (await http.get(f"{API}/users/staff", headers=_h(world["admin"]))).json()
    assert any(u["phone"] == "08000000000" for u in a)
