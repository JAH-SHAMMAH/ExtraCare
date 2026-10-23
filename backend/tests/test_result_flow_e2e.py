"""End-to-end: a class teacher runs Year 10 Amethyst's 2026/2027 Summer report.

Over real HTTP (auth + route permission checks run), as the people involved:
  teacher (class teacher, Maths via a Teaching Assignment, NO timetable slot)
    -> opens the entry grid -> enters marks -> comments -> checks readiness -> submits
  admin -> reviews -> approves -> publishes
and the negatives: a teacher cannot enter another subject, cannot approve, and a
parent sees nothing until it is published.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db
from app.core.security import create_access_token
from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.academics import StudentSubjectEnrollment
from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, AcademicTerm, Assessment, ClassPcTeacher,
)
from app.models.modules.school import (
    ParentGuardian, SchoolClass, Student, Subject, TeachingAssignment,
)
from tests.conftest import ensure_section

pytestmark = pytest.mark.asyncio
API = "/api/v1"


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.id})}"}


async def _user(db, org, preset, name):
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{name.lower()}-{uuid.uuid4().hex[:5]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


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
    org.onboarding_completed_at = None
    teacher = await _user(db, org, "teacher", "Zin")
    other = await _user(db, org, "teacher", "Other")
    admin = await _user(db, org, "org_admin", "Admin")
    parent = await _user(db, org, "parent", "Parent")
    sec = await ensure_section(db, org)
    sess = AcademicSession(id=str(uuid.uuid4()), name="2026/2027", term="Summer",
                           start_date=date(2026, 9, 14), end_date=date(2027, 7, 9),
                           is_current=True, org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Summer", position=3, is_active=True, org_id=org.id)
    sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10 Amethyst", level="Year 10", section="Amethyst",
                      section_id=sec.id, teacher_id=teacher.id, org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=sec.id, org_id=org.id)
    eng = Subject(id=str(uuid.uuid4()), name="English", section_id=sec.id, org_id=org.id)
    db.add_all([sess, term, sub, cls, maths, eng])
    await db.commit()
    ca = Assessment(id=str(uuid.uuid4()), name="CA", max_score=40, session_id=sess.id,
                    term_id=term.id, sub_term_id=sub.id, org_id=org.id)
    ex = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=60, session_id=sess.id,
                    term_id=term.id, sub_term_id=sub.id, org_id=org.id)
    studs = [Student(id=str(uuid.uuid4()), student_id=f"Y10-{i}", first_name=n, last_name="Test",
                     class_id=cls.id, org_id=org.id) for i, n in enumerate(["Ada", "Bola", "Chi"])]
    db.add_all([ca, ex, *studs])
    db.add(TeachingAssignment(id=str(uuid.uuid4()), class_id=cls.id, subject_id=maths.id,
                              teacher_id=teacher.id, org_id=org.id))
    db.add(TeachingAssignment(id=str(uuid.uuid4()), class_id=cls.id, subject_id=eng.id,
                              teacher_id=other.id, org_id=org.id))
    await db.commit()
    from tests._enrolment import enrol
    await enrol(db, org, studs, [maths, eng], academic_year="2026/2027")
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=studs[0].id,
                          relationship_type="parent", is_primary=True, org_id=org.id))
    await db.commit()
    return dict(teacher=teacher, other=other, admin=admin, parent=parent, cls=cls, maths=maths,
                eng=eng, term=term, sub=sub, sess=sess, ca=ca, ex=ex, studs=studs)


async def test_year10_amethyst_summer_report_end_to_end(http, db, org, world):
    w = world
    T, A = _h(w["teacher"]), _h(w["admin"])
    q = dict(class_id=w["cls"].id, subject_id=w["maths"].id, term_id=w["term"].id,
             sub_term_id=w["sub"].id, session_id=w["sess"].id)

    # 1. the teacher opens the Maths grid: 3 pupils, 2 columns (no timetable slot needed)
    r = await http.get(f"{API}/platform/report-entry", params=q, headers=T)
    assert r.status_code == 200, r.text
    g = r.json()
    assert len(g["students"]) == 3 and {a["name"] for a in g["assessments"]} == {"CA", "EXAM"}

    # 2. enters marks
    items = []
    for i, s in enumerate(w["studs"]):
        items += [dict(student_id=s.id, assessment_id=w["ca"].id, score=30 + i),
                  dict(student_id=s.id, assessment_id=w["ex"].id, score=40 + i)]
    r = await http.post(f"{API}/platform/report-entry", headers=T,
                        json=dict(subject_id=w["maths"].id, class_id=w["cls"].id, items=items))
    assert r.status_code == 200, r.text
    g = (await http.get(f"{API}/platform/report-entry", params=q, headers=T)).json()
    assert float(g["scores"][w["studs"][0].id][w["ca"].id]) == 30.0, "marks must persist"

    # 3. an over-max mark is refused, not silently stored
    r = await http.post(f"{API}/platform/report-entry", headers=T, json=dict(
        subject_id=w["maths"].id, class_id=w["cls"].id,
        items=[dict(student_id=w["studs"][0].id, assessment_id=w["ca"].id, score=999)]))
    assert r.status_code in (400, 422), r.text

    # 4. cannot enter English (another teacher's subject)
    r = await http.post(f"{API}/platform/report-entry", headers=T, json=dict(
        subject_id=w["eng"].id, class_id=w["cls"].id,
        items=[dict(student_id=w["studs"][0].id, assessment_id=w["ca"].id, score=10)]))
    assert r.status_code == 403

    # 5. the class teacher writes the PC comment; head comment is admin-only
    cm = dict(term_id=w["term"].id, sub_term_id=w["sub"].id, class_id=w["cls"].id,
              items=[dict(student_id=s.id, text="Good effort.") for s in w["studs"]])
    r = await http.post(f"{API}/platform/report-comments", headers=T, json=dict(kind="pc", **cm))
    assert r.status_code == 200, r.text
    r = await http.post(f"{API}/platform/report-comments", headers=T, json=dict(kind="head", **cm))
    assert r.status_code == 403
    r = await http.post(f"{API}/platform/report-comments", headers=A, json=dict(kind="head", **cm))
    assert r.status_code == 200, r.text

    # 6. readiness is readable, then submit to the admin
    r = await http.get(f"{API}/academics/report-workflow/subject-readiness", headers=T,
                       params=dict(class_id=w["cls"].id, term_id=w["term"].id, sub_term_id=w["sub"].id))
    assert r.status_code == 200, r.text
    r = await http.post(f"{API}/academics/report-workflow/submit", headers=T,
                        json=dict(class_id=w["cls"].id, term_id=w["term"].id, notes="Ready for review"))
    assert r.status_code in (200, 201), r.text
    wf = r.json()
    assert wf["stage"] == "submitted" and wf["class_name"] == "Year 10 Amethyst"

    # 7. it shows in the teacher's own list and the admin's queue
    mine = (await http.get(f"{API}/academics/report-workflow/mine", headers=T)).json()
    assert any(i["id"] == wf["id"] for i in mine["items"])
    queue = await http.get(f"{API}/academics/report-workflow", headers=A)
    assert queue.status_code == 200 and any(i["id"] == wf["id"] for i in queue.json()["items"])

    # 8. the teacher cannot approve or publish; submitting is not releasing
    for stage in ("reviewed", "approved", "published"):
        r = await http.patch(f"{API}/academics/report-workflow/{wf['id']}", headers=T, json=dict(stage=stage))
        assert r.status_code == 403, (stage, r.text)
    pq = dict(student_id=w["studs"][0].id, term_id=w["term"].id, sub_term_id=w["sub"].id)
    r = await http.get(f"{API}/platform/report-card", params=pq, headers=_h(w["parent"]))
    assert r.status_code in (403, 404) or not r.json().get("subjects"), "parent must not see an unpublished report"

    # 9. admin cannot skip a rung, then walks it
    r = await http.patch(f"{API}/academics/report-workflow/{wf['id']}", headers=A, json=dict(stage="published"))
    assert r.status_code == 422
    for stage in ("reviewed", "approved", "published"):
        r = await http.patch(f"{API}/academics/report-workflow/{wf['id']}", headers=A, json=dict(stage=stage))
        assert r.status_code == 200, (stage, r.text)
        assert r.json()["stage"] == stage

    # 10. the parent now sees their own child's card, and not another child's
    r = await http.get(f"{API}/platform/report-card", params=pq, headers=_h(w["parent"]))
    assert r.status_code == 200, r.text
    r = await http.get(f"{API}/platform/report-card", headers=_h(w["parent"]),
                       params=dict(pq, student_id=w["studs"][1].id))
    assert r.status_code in (403, 404)
