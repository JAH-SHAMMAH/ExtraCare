import json
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.platform import SchoolSection
from app.models.modules.school import SchoolClass, Subject, TeachingAssignment
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import _teacher_assignments
from app.routers.modules.school import (
    bulk_create_teachers, set_teaching_assignments, teaching_assignments_overview,
)
from app.routers.users import create_new_user
from app.schemas.teacher import BulkTeacherRequest, BulkTeacherRow, TeachingAssignmentsUpdate, TeachingPair
from app.schemas.user import UserCreate
from app.services.teaching import match_subject

pytestmark = pytest.mark.asyncio


class _Client:
    host = "127.0.0.1"


class _Req:
    headers = {}
    client = _Client()


class _S:  # minimal subject stand-in for the pure matcher
    def __init__(self, name, code=None):
        self.name, self.code = name, code


def test_match_subject_tiers():
    subs = [_S("Christian Religious Studies"), _S("Information and Communication Technology"),
            _S("Biology"), _S("French"), _S("Mathematics"), _S("Further Mathematics")]
    assert match_subject("CRS", subs)[0].name == "Christian Religious Studies"
    assert match_subject("ICT", subs)[0].name == "Information and Communication Technology"
    assert match_subject("biology", subs)[0].name == "Biology"
    assert match_subject("Mathematics", subs)[0].name == "Mathematics"      # exact beats "Further Mathematics"
    assert match_subject("Maths", subs)[0] is None                            # not guessed
    assert match_subject("Latin", subs)[0] is None
    two = [_S("Art Studies"), _S("Art History")]
    subj, why = match_subject("Art", two)
    assert subj is None and "more than one" in why


async def _world(db, org):
    sec = {n: SchoolSection(id=str(uuid.uuid4()), name=n, org_id=org.id) for n in ("Primary", "Secondary")}
    db.add_all(sec.values())
    await db.flush()
    classes = {n: SchoolClass(id=str(uuid.uuid4()), name=n, level=n, section_id=sec[s].id, org_id=org.id)
               for n, s in (("Year 5", "Primary"), ("Year 6", "Primary"), ("SS 1", "Secondary"), ("SS 2", "Secondary"))}
    subjects = {n: Subject(id=str(uuid.uuid4()), name=n, section_id=sec[s].id, org_id=org.id)
                for n, s in (("French", "Primary"), ("Biology", "Secondary"),
                             ("Christian Religious Studies", "Secondary"))}
    role = Role(id=str(uuid.uuid4()), name="Teacher", slug="teacher", permissions=["school:read"], org_id=org.id, is_system=False)
    arole = Role(id=str(uuid.uuid4()), name="Admin", slug="admin", permissions=["*"], org_id=org.id, is_system=False)
    admin = User(id=str(uuid.uuid4()), email="head@fv.com", full_name="Head", status=UserStatus.ACTIVE, org_id=org.id)
    admin.roles = [arole]
    db.add_all([*classes.values(), *subjects.values(), role, arole, admin])
    await db.commit()
    return sec, classes, subjects, role, admin


async def test_bulk_add_links_the_subject_to_the_whole_section(db, org):
    sec, classes, subjects, role, admin = await _world(db, org)
    rows = [BulkTeacherRow(first_name="Jeremiah", subject="CRS", department="secondary"),
            BulkTeacherRow(first_name="Juliet", subject="French", department="primary"),
            BulkTeacherRow(first_name="Isaiah", subject="ICT", department="primary")]   # no ICT subject
    res = await bulk_create_teachers(BulkTeacherRequest(rows=rows), _Req(), db=db, current_user=admin)
    await db.commit()
    body = json.loads(res.body)
    jer, jul, isa = body["rows"]
    assert jer["subject_matched"] == "Christian Religious Studies" and jer["assigned_classes"] == 2
    assert jul["subject_matched"] == "French" and jul["assigned_classes"] == 2
    assert isa["subject_matched"] is None and "not linked" in isa["subject_note"] and isa["status"] == "ok"
    u = (await db.execute(select(User).where(User.email == "jeremiah@fv.com"))).scalar_one()
    pairs = await _teacher_assignments(db, org.id, u.id)
    assert pairs == {(classes["SS 1"].id, subjects["Christian Religious Studies"].id),
                     (classes["SS 2"].id, subjects["Christian Religious Studies"].id)}


async def test_two_teachers_can_share_a_subject(db, org):
    sec, classes, subjects, role, admin = await _world(db, org)
    res = await bulk_create_teachers(BulkTeacherRequest(rows=[
        BulkTeacherRow(first_name="Ada", subject="Biology", department="secondary"),
        BulkTeacherRow(first_name="Bola", subject="Biology", department="secondary")]), _Req(), db=db, current_user=admin)
    await db.commit()
    assert json.loads(res.body)["created"] == 2
    assert len((await db.execute(select(TeachingAssignment))).scalars().all()) == 4


async def test_overview_and_replace(db, org):
    sec, classes, subjects, role, admin = await _world(db, org)
    await bulk_create_teachers(BulkTeacherRequest(rows=[
        BulkTeacherRow(first_name="Ada", subject="Biology", department="secondary")]), _Req(), db=db, current_user=admin)
    await db.commit()
    t = (await db.execute(select(User).where(User.email == "ada@fv.com"))).scalar_one()
    classes["SS 1"].teacher_id = t.id
    await db.commit()
    ov = await teaching_assignments_overview(section=None, db=db, current_user=admin)
    row = [i for i in ov["items"] if i["id"] == t.id][0]
    assert row["sections"] == ["Secondary"] and [c["name"] for c in row["class_teacher_of"]] == ["SS 1"]
    assert len(row["assignments"]) == 2

    # narrow to SS 1 only
    await set_teaching_assignments(t.id, TeachingAssignmentsUpdate(
        pairs=[TeachingPair(class_id=classes["SS 1"].id, subject_id=subjects["Biology"].id)]),
        request=_Req(), db=db, current_user=admin)
    await db.commit()
    assert await _teacher_assignments(db, org.id, t.id) == {(classes["SS 1"].id, subjects["Biology"].id)}
    with pytest.raises(HTTPException):
        await set_teaching_assignments(t.id, TeachingAssignmentsUpdate(
            pairs=[TeachingPair(class_id=str(uuid.uuid4()), subject_id=subjects["Biology"].id)]),
            request=_Req(), db=db, current_user=admin)


async def test_create_user_form_subjects(db, org):
    sec, classes, subjects, role, admin = await _world(db, org)
    data = UserCreate(email="new@fv.com", full_name="New Teacher", password="Temp12345", role_ids=[role.id],
                      section_ids=[sec["Primary"].id], subject_ids=[subjects["French"].id])
    await create_new_user(data, _Req(), db=db, current_user=admin)
    await db.commit()
    u = (await db.execute(select(User).where(User.email == "new@fv.com"))).scalar_one()
    assert await _teacher_assignments(db, org.id, u.id) == {
        (classes["Year 5"].id, subjects["French"].id), (classes["Year 6"].id, subjects["French"].id)}
