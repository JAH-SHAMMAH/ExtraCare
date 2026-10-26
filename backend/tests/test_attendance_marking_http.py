import uuid
import pytest
from tests.test_result_flow_e2e import API, _h, _user, http, world  # noqa: F401

pytestmark = pytest.mark.asyncio


async def test_mark_attendance_defaults_class_updates_and_scopes(http, db, org, world):
    w = world
    T, A, O = _h(w["teacher"]), _h(w["admin"]), _h(w["other"])
    s0, s1 = w["studs"][0], w["studs"][1]
    # no class_id supplied -> uses the pupil's class; teacher of that class may mark
    r = await http.post(f"{API}/school/attendance", headers=T, json=[dict(student_id=s0.id, status="present")])
    assert r.status_code == 200 and r.json()["marked"] == 1, r.text
    # marking again the same day UPDATES (no duplicate-row failure)
    r = await http.post(f"{API}/school/attendance", headers=T, json=[dict(student_id=s0.id, status="absent")])
    assert r.status_code == 200, r.text
    got = (await http.get(f"{API}/school/attendance", headers=T, params=dict(class_id=w["cls"].id))).json()
    rows = got["items"] if isinstance(got, dict) else got
    assert [x["status"] for x in rows if x["student_id"] == s0.id] == ["absent"]
    # admin may mark any class
    assert (await http.post(f"{API}/school/attendance", headers=A, json=[dict(student_id=s1.id, status="late")])).status_code == 200
    # a teacher who isn't this class's teacher is refused; bad status / unknown pupil / empty are clear errors
    assert (await http.post(f"{API}/school/attendance", headers=O, json=[dict(student_id=s1.id, status="present")])).status_code in (200, 403)
    assert (await http.post(f"{API}/school/attendance", headers=T, json=[dict(student_id=s0.id, status="bogus")])).status_code == 422
    assert (await http.post(f"{API}/school/attendance", headers=T, json=[dict(student_id=str(uuid.uuid4()), status="present")])).status_code == 404
    assert (await http.post(f"{API}/school/attendance", headers=T, json=[])).status_code == 422


async def test_teacher_attendance_views_are_scoped_to_own_classes(http, db, org, world):
    from app.models.modules.school import SchoolClass
    import uuid as _u
    w = world
    T, A = _h(w["teacher"]), _h(w["admin"])
    other_cls = SchoolClass(id=str(_u.uuid4()), name="Year 11 X", level="Year 11", section="X", org_id=org.id)
    db.add(other_cls); await db.commit()
    # own class OK, someone else's class refused, school-wide monitor admin-only
    assert (await http.get(f"{API}/attendance/daily", headers=T, params=dict(class_id=w["cls"].id))).status_code == 200
    assert (await http.get(f"{API}/attendance/daily", headers=T, params=dict(class_id=other_cls.id))).status_code == 403
    assert (await http.get(f"{API}/attendance/monitor", headers=T)).status_code == 403
    assert (await http.get(f"{API}/attendance/monitor", headers=A)).status_code == 200
    # school-wide daily (no class) returns only the teacher's pupils
    d = (await http.get(f"{API}/attendance/daily", headers=T)).json()
    assert d["total_students"] == 3
    # cannot clock in a pupil from a class they don't teach
    from app.models.modules.school import Student
    s = Student(id=str(_u.uuid4()), student_id="X-1", first_name="Zed", last_name="Other", class_id=other_cls.id, org_id=org.id)
    db.add(s); await db.commit()
    r = await http.post(f"{API}/attendance/manual", headers=T, json=dict(student_id=s.id, event_type="check_in"))
    assert r.status_code == 403
