import json
import uuid

import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.models.modules.platform import SchoolSection
from app.models.modules.school import TeacherSection
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.auth import get_me
from app.routers.modules.school import bulk_create_teachers
from app.schemas.teacher import BulkTeacherRequest, BulkTeacherRow
from app.services.teacher_bulk import email_for, temp_password

pytestmark = pytest.mark.asyncio


class _Client:
    host = "127.0.0.1"


class _Req:  # log_action only reads headers/client
    headers = {}
    client = _Client()


async def _setup(db, org):
    for n in ("Early Years", "Primary", "Secondary"):
        db.add(SchoolSection(id=str(uuid.uuid4()), name=n, org_id=org.id,
                             curriculum="EYFS" if n == "Early Years" else None))
    role = Role(id=str(uuid.uuid4()), name="Teacher", slug="teacher", permissions=["school:read"],
                org_id=org.id, is_system=False)
    admin_role = Role(id=str(uuid.uuid4()), name="Admin", slug="admin", permissions=["*"],
                      org_id=org.id, is_system=False)
    admin = User(id=str(uuid.uuid4()), email="headadmin@fairviewschoolng.com", full_name="Head",
                 status=UserStatus.ACTIVE, org_id=org.id)
    admin.roles = [admin_role]
    db.add_all([role, admin_role, admin])
    await db.commit()
    return admin


def _rows():
    return [
        BulkTeacherRow(first_name="Jeremiah", title="Mr", subject="CRS", department="secondary"),
        BulkTeacherRow(first_name="Chiamaka", title="Ms", subject="Biology", department="secondary"),
        BulkTeacherRow(first_name="Juliet", title="Mrs", subject="French", department="primary"),
        BulkTeacherRow(first_name="Isaiah", title="Mr", subject="ICT", department="primary"),
    ]


async def _call(db, admin, rows, dry_run=False):
    res = await bulk_create_teachers(BulkTeacherRequest(rows=rows, dry_run=dry_run), _Req(), db=db, current_user=admin)
    return json.loads(res.body)


async def test_creates_the_four_with_name_emails_roles_sections_and_forced_password(db, org):
    admin = await _setup(db, org)
    body = await _call(db, admin, _rows())
    await db.commit()
    assert body["created"] == 4 and body["skipped"] == 0
    by_email = {r["email"]: r for r in body["rows"]}
    assert set(by_email) == {f"{n}@fairviewschoolng.com" for n in ("jeremiah", "chiamaka", "juliet", "isaiah")}
    for email, r in by_email.items():
        u = (await db.execute(select(User).where(User.email == email))).scalar_one()
        assert u.force_password_change is True and u.status == UserStatus.ACTIVE
        assert verify_password(r["temporary_password"], u.hashed_password)
        assert [x.slug for x in u.roles] == ["teacher"]
    sec = {(await db.execute(select(SchoolSection.name).where(SchoolSection.id == ts.section_id))).scalar_one()
           for ts in (await db.execute(select(TeacherSection))).scalars().all()}
    assert sec == {"Primary", "Secondary"}
    jer = (await db.execute(select(User).where(User.email == "jeremiah@fairviewschoolng.com"))).scalar_one()
    assert [s.name for s in (await get_me(current_user=jer, db=db)).teacher_sections] == ["Secondary"]
    assert (await get_me(current_user=jer, db=db)).force_password_change is True


async def test_dry_run_creates_nothing_and_returns_no_passwords(db, org):
    admin = await _setup(db, org)
    body = await _call(db, admin, _rows(), dry_run=True)
    assert body["created"] == 0 and all("temporary_password" not in r for r in body["rows"])
    assert (await db.execute(select(User).where(User.email == "juliet@fairviewschoolng.com"))).first() is None


async def test_taken_email_and_unknown_department_are_skipped_not_fatal(db, org):
    admin = await _setup(db, org)
    rows = _rows() + [
        BulkTeacherRow(first_name="Jeremiah", title="Mr", subject="Maths", department="secondary"),   # duplicate in list
        BulkTeacherRow(first_name="Ngozi", subject="Art", department="astronomy"),                       # no such section
    ]
    body = await _call(db, admin, rows)
    assert body["created"] == 4 and body["skipped"] == 2
    statuses = [r["status"] for r in body["rows"]]
    assert statuses == ["ok", "ok", "ok", "ok", "conflict", "error"]
    # Running it again must not duplicate anyone.
    again = await _call(db, admin, _rows())
    assert again["created"] == 0 and all(r["status"] == "conflict" for r in again["rows"])


async def test_helpers():
    assert email_for("Chiamaka", "fairviewschoolng.com") == "chiamaka@fairviewschoolng.com"
    assert email_for("José-Ana", "x.com") == "joseana@x.com"
    assert email_for("", "x.com") is None
    pw = temp_password()
    assert len(pw) == 10 and not set(pw) & set("0O1lI")


async def test_request_exactly_as_the_page_sends_it(db, org):
    """The page posts last_name "" and nulls for blanks; that must validate."""
    payload = {"dry_run": True, "rows": [
        {"title": "Mr", "first_name": "Jeremiah", "last_name": "", "subject": "CRS",
         "department": "secondary", "email": None},
        {"title": None, "first_name": "Ada", "last_name": None, "subject": None,
         "department": "", "email": ""},
    ]}
    req = BulkTeacherRequest.model_validate(payload)
    assert [r.last_name for r in req.rows] == ["", ""]
    assert req.rows[1].department is None and req.rows[1].email is None
    admin = await _setup(db, org)
    body = await _call(db, admin, req.rows, dry_run=True)
    assert [r["name"] for r in body["rows"]] == ["Jeremiah", "Ada"]
