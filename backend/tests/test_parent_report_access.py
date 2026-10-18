"""A parent reads their own child's published report, and nothing else.

~~~ WHY THIS IS AT THE HTTP LAYER ~~~
The gate being tested IS a FastAPI dependency. `PermissionChecker` runs only
when a request goes through the app, so a test that calls the handler function
directly never evaluates it -- it proves the in-handler ownership logic and
says nothing about who was let in. Both halves matter here, so every assertion
below goes over the real stack with a real bearer token.

~~~ WHAT WENT WRONG ~~~
The parent preset carried `school:reports:read`, which is also the scope the
staff report screens are gated on. One scope was doing two unrelated jobs:
"may read reports across the school" and "may read my own child's card". So a
parent held the staff scope, three staff report groups appeared in their
sidebar, and -- far worse than the menu -- `/report-cards-bulk` took a class id
and returned EVERY pupil's report card in it with no ownership check at all.

The fix splits them: `school:reports:own:read` for a parent or pupil reading
their own, `school:reports:read` for staff reading across the school. Nothing
here keys on a role NAME; a parent is simply someone who does not hold the
staff scope.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.database import get_db
from app.main import app
from app.models.modules.school import ParentGuardian, SchoolClass, Student
from app.models.organization import SubscriptionTier
from app.models.role import SCHOOL_PERMISSION_PRESETS, Role
from app.models.user import User, UserStatus

pytestmark = pytest.mark.asyncio

API = "/api/v1/platform"

#: Every staff report surface behind the menu groups a parent could see, with
#: the menu item that led there. A parent must be refused by all of them.
#:
#: `/report-cards-bulk` is the one that mattered: gated on the scope the parent
#: held, and with no ownership check inside, so it answered for a whole class.
STAFF_REPORT_ROUTES = [
    ("/report-cards-bulk", {"class_id": "x", "term_id": "t", "sub_term_id": "s"}, "Reports View"),
    ("/report-broadsheet", {"class_id": "x", "term_id": "t", "sub_term_id": "s"}, "Make Report"),
    ("/report-entry", {"class_id": "x", "subject_id": "y", "term_id": "t", "sub_term_id": "s"}, "Report Entry"),
    ("/report-insight", {"class_id": "x", "term_id": "t", "sub_term_id": "s"}, "Grade Analysis"),
    ("/result-analysis/subjects", {"term_id": "t", "sub_term_id": "s"}, "Result Analysis"),
    ("/result-analysis/honour-roll", {"term_id": "t", "sub_term_id": "s"}, "Result Analysis"),
    ("/result-analysis/remedial", {"term_id": "t", "sub_term_id": "s"}, "Result Analysis"),
    ("/result-analysis/performance-tracker", {"term_id": "t", "sub_term_id": "s"}, "Result Analysis"),
    ("/result-analysis/my-classes", {}, "Result Analysis"),
    ("/result-analysis/grade-summary", {"term_id": "t", "sub_term_id": "s"}, "Grade Analysis"),
    ("/result-analysis/order-of-merit", {"term_id": "t", "sub_term_id": "s"}, "Result Analysis"),
    ("/result-analysis/departmental", {"term_id": "t", "sub_term_id": "s"}, "Result Analysis"),
    ("/result-analysis/academic-alert", {"term_id": "t", "sub_term_id": "s"}, "Result Analysis"),
    ("/result-analysis/subject-performance", {"term_id": "t", "sub_term_id": "s"}, "Result Analysis"),
]


async def _preset_user(db, org, preset: str, email: str | None = None) -> User:
    """A user carrying a REAL preset from SCHOOL_PERMISSION_PRESETS.

    Not a hand-picked scope list: the whole point is to catch the preset
    granting something it should not.
    """
    u = User(id=str(uuid.uuid4()), email=email or f"{preset}-{uuid.uuid4().hex[:6]}@x.com",
             full_name=preset.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id,
                is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}


@pytest_asyncio.fixture
async def http(db):
    """The real app over the test session, so the whole dependency chain runs."""
    async def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def family(db, org):
    """A parent with one child, plus somebody else's child in the same class.

    Enterprise tier so the plan/module gate is satisfied and a refusal can only
    come from the PERMISSION gate -- otherwise a 403 proves nothing about RBAC.
    """
    org.subscription_tier = SubscriptionTier.ENTERPRISE
    db.add(org)

    klass = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    db.add(klass)
    await db.flush()

    parent = await _preset_user(db, org, "parent")

    mine = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}",
                   first_name="Mine", last_name="Child", class_id=klass.id, org_id=org.id)
    theirs = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}",
                     first_name="Someone", last_name="Else", class_id=klass.id, org_id=org.id)
    db.add_all([mine, theirs])
    await db.flush()

    db.add(ParentGuardian(user_id=parent.id, student_id=mine.id,
                          relationship_type="parent", is_primary=True, org_id=org.id))
    await db.commit()
    return {"parent": parent, "mine": mine, "theirs": theirs, "class": klass, "org": org}


# -- the preset itself -------------------------------------------------------

async def test_the_parent_preset_does_not_carry_the_staff_report_scope(db, org):
    """The root cause, asserted on the preset rather than on a symptom.

    `school:reports:read` is what every staff report screen is gated on. A
    parent must not hold it, directly or through the broad->fine hierarchy.
    """
    parent = await _preset_user(db, org, "parent")

    assert not parent.has_permission("school:reports:read"), (
        "the parent preset grants the STAFF report scope. Every screen gated on "
        "it opens, including /report-cards-bulk, which returns a whole class's "
        "report cards and has no ownership check inside."
    )
    assert parent.has_permission("school:reports:own:read"), (
        "a parent must still hold the own-child read scope, or their own report "
        "card page breaks and shows an empty state that reads as 'not published'"
    )
    assert not parent.has_permission("school:reports:write")
    assert not parent.has_permission("school_admin:read")


async def test_the_pupil_preset_is_narrowed_the_same_way(db, org):
    """A pupil held the identical scope, so the same staff screens opened for
    them too. Not mentioned in the original report, found while fixing it."""
    student = await _preset_user(db, org, "student")

    assert not student.has_permission("school:reports:read"), (
        "the student preset grants the staff report scope"
    )
    assert student.has_permission("school:reports:own:read")


# -- the staff surfaces ------------------------------------------------------

@pytest.mark.parametrize("path,params,menu_item", STAFF_REPORT_ROUTES,
                         ids=[r[0] for r in STAFF_REPORT_ROUTES])
async def test_a_parent_is_refused_every_staff_report_route(http, family, path, params, menu_item):
    """403 from the gate, not data, and not a 404 that merely hides the answer.

    A 404 would be a weaker result: it would mean the parent got past the
    permission gate and was stopped by a missing row, which is luck rather than
    access control.
    """
    r = await http.get(f"{API}{path}", params=params, headers=_bearer(family["parent"]))
    assert r.status_code == 403, (
        f"{path} (behind the '{menu_item}' menu item) answered {r.status_code} "
        f"for a parent, not 403. Body: {r.text[:200]}"
    )


async def test_the_bulk_endpoint_would_have_exposed_the_whole_class(http, family):
    """Named separately because it is the one with real pupil data behind it.

    /report-cards-bulk takes a class id and returns every pupil's card in it.
    It had no ownership check at all -- only the scope gate, which the parent
    held. One request with any class id was a whole class's reports.
    """
    r = await http.get(f"{API}/report-cards-bulk",
                       params={"class_id": family["class"].id, "term_id": "t",
                               "sub_term_id": "s"},
                       headers=_bearer(family["parent"]))
    assert r.status_code == 403, (
        f"a parent read /report-cards-bulk for class {family['class'].id} and got "
        f"{r.status_code}. This endpoint has no per-pupil ownership check, so "
        f"anything but 403 here is every pupil's report card in that class."
    )


# -- what the parent keeps ---------------------------------------------------

async def test_a_parent_still_reaches_their_own_childs_report_card(http, family):
    """The gate must not be so tight that the parent's own page breaks.

    Anything but 403 is acceptable here: a 200 with the card, or a 404 when no
    report exists for the term, are both the endpoint working. A 403 would mean
    the fix cut off the one thing a parent is for.
    """
    r = await http.get(f"{API}/report-card",
                       params={"student_id": family["mine"].id, "term_id": "t",
                               "sub_term_id": "s"},
                       headers=_bearer(family["parent"]))
    assert r.status_code != 403, (
        f"a parent was refused their OWN child's report card ({r.status_code}): "
        f"{r.text[:200]}. The own-child scope is missing from the route's gate."
    )


async def test_a_parent_cannot_read_another_childs_report_card(http, family):
    """The ownership check inside the handler, over HTTP.

    This is the half that already worked -- `_ensure_student_visible` plus
    `_user_owns_student` -- and it must keep working, because the scope split
    above deliberately leaves this route reachable by parents.
    """
    r = await http.get(f"{API}/report-card",
                       params={"student_id": family["theirs"].id, "term_id": "t",
                               "sub_term_id": "s"},
                       headers=_bearer(family["parent"]))
    assert r.status_code in (403, 404), (
        f"a parent read another family's child ({r.status_code}): {r.text[:200]}"
    )


async def test_a_parent_can_list_sessions_for_the_report_card_picker(http, family):
    """The Session dropdown on the report card reads /sessions. It was staff-only,
    so a parent's dropdown came back empty with nothing to pick."""
    r = await http.get(f"{API}/sessions", headers=_bearer(family["parent"]))
    assert r.status_code == 200, f"parent refused the session list ({r.status_code}): {r.text[:200]}"
