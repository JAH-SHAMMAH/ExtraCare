"""A pupil lists their own teachers and rates them; nobody else's, and not others' teachers."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
import pytest_asyncio

from app.main import app
from app.database import get_db
from app.models.modules.school import SchoolClass, Student, Subject, Timetable
from app.models.organization import SubscriptionTier
from tests.conftest import ensure_section
from tests.test_parent_report_access import _preset_user, _bearer, API  # noqa: F401

pytestmark = pytest.mark.asyncio
BASE = "/api/v1/school"


@pytest_asyncio.fixture
async def http(db):
    async def _get_db():
        yield db
    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def world(db, org):
    org.subscription_tier = SubscriptionTier.ENTERPRISE
    db.add(org)
    mine_cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    other_cls = SchoolClass(id=str(uuid.uuid4()), name="JSS2 A", level="Secondary", org_id=org.id)
    db.add_all([mine_cls, other_cls])
    await db.flush()
    pupil = await _preset_user(db, org, "student")
    my_teacher = await _preset_user(db, org, "teacher")
    other_teacher = await _preset_user(db, org, "teacher")
    sec = await ensure_section(db, org)
    maths = Subject(id=str(uuid.uuid4()), name="Maths", section_id=sec.id, org_id=org.id)
    eng = Subject(id=str(uuid.uuid4()), name="English", section_id=sec.id, org_id=org.id)
    db.add_all([maths, eng])
    await db.flush()
    st = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}", first_name="Ada", last_name="O",
                 class_id=mine_cls.id, user_id=pupil.id, org_id=org.id)
    db.add(st)
    db.add(Timetable(class_id=mine_cls.id, subject_id=maths.id, day_of_week=0, start_time="08:00",
                     end_time="09:00", teacher_id=my_teacher.id, org_id=org.id))
    db.add(Timetable(class_id=other_cls.id, subject_id=eng.id, day_of_week=0, start_time="08:00",
                     end_time="09:00", teacher_id=other_teacher.id, org_id=org.id))
    await db.commit()
    return {"pupil": pupil, "mine": my_teacher, "other": other_teacher}


async def test_pupil_sees_only_their_own_teachers(http, world):
    r = await http.get(f"{BASE}/my-teachers", headers=_bearer(world["pupil"]))
    assert r.status_code == 200, r.text
    ids = [t["teacher_id"] for t in r.json()]
    assert ids == [world["mine"].id]
    assert r.json()[0]["subjects"] == ["Maths"]


async def test_pupil_can_rate_and_change_a_rating(http, world):
    h = _bearer(world["pupil"])
    url = f"{BASE}/my-teachers/{world['mine'].id}/rating"
    assert (await http.put(url, json={"rating": 4, "comment": "Clear"}, headers=h)).status_code == 200
    assert (await http.put(url, json={"rating": 5}, headers=h)).status_code == 200
    got = (await http.get(f"{BASE}/my-teachers", headers=h)).json()[0]
    assert got["my_rating"] == 5


async def test_pupil_cannot_rate_a_teacher_who_does_not_teach_them(http, world):
    r = await http.put(f"{BASE}/my-teachers/{world['other'].id}/rating", json={"rating": 1},
                       headers=_bearer(world["pupil"]))
    assert r.status_code == 403


async def test_rating_must_be_one_to_five(http, world):
    r = await http.put(f"{BASE}/my-teachers/{world['mine'].id}/rating", json={"rating": 9},
                       headers=_bearer(world["pupil"]))
    assert r.status_code == 422


async def test_anonymous_rating_hides_the_pupil_from_admin(http, db, org, world):
    h = _bearer(world["pupil"])
    r = await http.put(f"{BASE}/my-teachers/{world['mine'].id}/rating",
                       json={"rating": 3, "comment": "Fast", "anonymous": True}, headers=h)
    assert r.status_code == 200 and r.json()["my_anonymous"] is True
    admin = await _preset_user(db, org, "org_admin")
    ra = await http.get(f"{BASE}/ratings", headers=_bearer(admin))
    item = ra.json()["items"][0]
    assert item["student_name"] == "Anonymous" and item["student_id"] is None and item["comment"] == "Fast"
    s = (await http.get(f"{BASE}/ratings/summary", headers=_bearer(admin))).json()
    assert s[0]["teacher_id"] == world["mine"].id and s[0]["average"] == 3 and s[0]["count"] == 1


async def test_named_rating_shows_the_pupil_to_admin(http, db, org, world):
    await http.put(f"{BASE}/my-teachers/{world['mine'].id}/rating", json={"rating": 5},
                   headers=_bearer(world["pupil"]))
    admin = await _preset_user(db, org, "org_admin")
    item = (await http.get(f"{BASE}/ratings", headers=_bearer(admin))).json()["items"][0]
    assert item["student_name"] == "Ada O" and item["is_anonymous"] is False
