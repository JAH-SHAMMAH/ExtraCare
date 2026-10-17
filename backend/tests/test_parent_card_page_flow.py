"""The whole Report Cards page, as a parent, in the order the browser calls it.

~~~ WHY THIS FILE EXISTS ~~~
`42feaa3` split `school:reports:read` (staff) from `school:reports:own:read`
(own child). The sidebar came out right and the class-wide exposure closed, but
a parent could no longer see their child's card at all -- because the page does
not call the endpoint that was widened.

There are TWO report-card endpoints:

    GET /platform/report-card                      <- widened in 42feaa3
    GET /school/students/{student_id}/report-card  <- what the PAGE calls

The second is `schoolApi.grades.reportCard` in the frontend, and it was still
gated on the staff scope, so every parent got a 403 and the page rendered "No
report card available" -- which reads as "your child's report is not
published". The existing test suite did not catch it because
test_rbac_pentest.py calls `get_report_card` as a FUNCTION, which never
evaluates the route's dependency, and the new test only exercised the platform
route.

So this file drives the page's request SEQUENCE over HTTP, not one endpoint:
if any call in the chain 403s, the page is broken, and the test says which.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.database import get_db
from app.main import app
from app.models.modules.academics import ReportApproval
from app.models.modules.platform import AcademicTerm
from app.models.modules.school import (
    Grade, GradeStatus, ParentGuardian, SchoolClass, Student, Subject,
)
from app.models.organization import SubscriptionTier
from app.models.role import SCHOOL_PERMISSION_PRESETS, Role
from app.models.user import User, UserStatus
from tests.conftest import ensure_section

pytestmark = pytest.mark.asyncio

RELEASED_STAGE = "published"
TERM_NAME = "Autumn"

#: Every request the Report Cards page makes for a non-staff caller, in order.
#: `required` is True when a 403 leaves the page unable to show the card.
#:
#: /platform/grading-scales and /school/classes are listed and NOT required: a
#: parent never held `settings:read` or `school:classes:read`, before or after
#: the split, so their 403s are long-standing and the page copes. Including them
#: keeps the table honest about what the browser actually asks for.
PAGE_REQUESTS = [
    ("GET", "/api/v1/platform/academic-terms", {}, True, "term dropdown"),
    ("GET", "/api/v1/platform/academic-sub-terms", {}, True, "sub-term dropdown"),
    ("GET", "/api/v1/platform/sections", {}, True, "section filter"),
    ("GET", "/api/v1/school/students", {}, True, "which pupils are mine"),
    ("GET", "/api/v1/platform/grading-scales", {}, False, "grade bands (staff-only, always was)"),
    ("GET", "/api/v1/school/classes", {}, False, "class picker (staff-only, always was)"),
]


async def _preset_user(db, org, preset: str) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{preset}-{uuid.uuid4().hex[:6]}@x.com",
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
    async def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def school(db, org):
    """Chukwuma -> Musa, in a class whose Autumn term is PUBLISHED, with a mark.

    Modelled on the reported regression rather than on a minimal fixture: the
    card has to come back with data, so the published-stage approval and a
    PUBLISHED grade both have to be there. A 200 with an empty card would have
    looked like a pass and still been a broken page.
    """
    org.subscription_tier = SubscriptionTier.ENTERPRISE
    db.add(org)

    section = await ensure_section(db, org)
    klass = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    db.add(klass)
    await db.flush()

    subject = Subject(id=str(uuid.uuid4()), name="Mathematics",
                      section_id=section.id, org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name=TERM_NAME, org_id=org.id)
    db.add_all([subject, term])
    await db.flush()

    parent = await _preset_user(db, org, "parent")
    pupil_user = await _preset_user(db, org, "student")

    musa = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}",
                   first_name="Musa", last_name="Yusuf", class_id=klass.id,
                   user_id=pupil_user.id, org_id=org.id)
    other = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}",
                    first_name="Somebody", last_name="Else", class_id=klass.id,
                    org_id=org.id)
    db.add_all([musa, other])
    await db.flush()

    db.add(ParentGuardian(user_id=parent.id, student_id=musa.id,
                          relationship_type="parent", is_primary=True, org_id=org.id))
    # The school has signed Autumn off: both gates the endpoint checks.
    db.add(ReportApproval(id=str(uuid.uuid4()), class_id=klass.id, term_id=term.id,
                          stage=RELEASED_STAGE, org_id=org.id))
    db.add(Grade(id=str(uuid.uuid4()), student_id=musa.id, subject_id=subject.id,
                 term=TERM_NAME, score=78, max_score=100, grade_letter="B",
                 status=GradeStatus.PUBLISHED, org_id=org.id))
    # An unpublished term, to prove the published gate still bites.
    winter = AcademicTerm(id=str(uuid.uuid4()), name="Winter", org_id=org.id)
    db.add(winter)
    await db.flush()
    db.add(Grade(id=str(uuid.uuid4()), student_id=musa.id, subject_id=subject.id,
                 term="Winter", score=91, max_score=100, grade_letter="A",
                 status=GradeStatus.PUBLISHED, org_id=org.id))
    await db.commit()

    return {"parent": parent, "pupil_user": pupil_user, "musa": musa,
            "other": other, "class": klass, "term": term}


def _card_url(student_id: str) -> str:
    return f"/api/v1/school/students/{student_id}/report-card"


# -- the page, end to end ----------------------------------------------------

async def test_a_parent_can_load_every_request_the_page_makes(http, school):
    """The regression, as the browser experiences it.

    Each required call must not 403. The card request is checked separately
    below; this is everything the page needs around it.
    """
    headers = _bearer(school["parent"])
    refused = []
    for method, url, params, required, why in PAGE_REQUESTS:
        r = await http.request(method, url, params=params, headers=headers)
        if required and r.status_code == 403:
            refused.append(f"{method} {url} ({why})")
    assert not refused, (
        "a parent is refused these calls, so the Report Cards page cannot "
        f"assemble itself: {refused}"
    )


async def test_a_parent_sees_their_childs_published_card_with_data(http, school):
    """The actual complaint: Chukwuma opening Musa's Autumn report.

    Asserts DATA, not just a 200 -- a 200 carrying an empty grade list is the
    same broken page from the parent's point of view.
    """
    r = await http.get(_card_url(school["musa"].id), params={"term": TERM_NAME},
                       headers=_bearer(school["parent"]))

    assert r.status_code == 200, (
        f"a parent was refused their own child's card: {r.status_code} "
        f"{r.text[:200]}. This is the endpoint the PAGE calls -- "
        f"/school/students/{{id}}/report-card -- not /platform/report-card."
    )
    body = r.json()
    assert body["student_id"] == school["musa"].id
    grades = body.get("grades") or body.get("subjects") or []
    assert grades, (
        f"the card came back empty for a published term: {str(body)[:300]}. "
        f"A parent cannot tell an empty card from a refused one."
    )


async def test_a_pupil_sees_their_own_published_card(http, school):
    """The same endpoint, the other non-staff caller. A pupil held the identical
    scope, so they were refused the same way."""
    r = await http.get(_card_url(school["musa"].id), params={"term": TERM_NAME},
                       headers=_bearer(school["pupil_user"]))
    assert r.status_code == 200, f"a pupil was refused their own card: {r.text[:200]}"
    assert r.json()["student_id"] == school["musa"].id


# -- and what must still be refused ------------------------------------------

async def test_a_parent_cannot_load_an_unlinked_childs_card(http, school):
    """Widening the gate must not widen the data. The ownership check
    (`_ensure_student_visible`) is what scopes this, and it has to keep doing so
    now that a parent reaches the route at all."""
    r = await http.get(_card_url(school["other"].id), params={"term": TERM_NAME},
                       headers=_bearer(school["parent"]))
    assert r.status_code in (403, 404), (
        f"a parent loaded another family's child: {r.status_code} {r.text[:200]}"
    )


async def test_an_unpublished_term_shows_no_marks_to_a_parent(http, school):
    """The published gate, which is separate from the permission gate.

    Winter has a PUBLISHED grade row but no published ReportApproval, so the
    school has not released it. The parent may call the endpoint and must see
    nothing -- not the mark, and not someone else's either.
    """
    r = await http.get(_card_url(school["musa"].id), params={"term": "Winter"},
                       headers=_bearer(school["parent"]))
    assert r.status_code in (200, 404), r.text[:200]
    if r.status_code == 200:
        grades = r.json().get("grades") or r.json().get("subjects") or []
        assert not grades, (
            f"an unreleased term's marks reached a parent: {str(grades)[:200]}. "
            f"ReportApproval.stage is the school's sign-off and it is not "
            f"'published' for this term."
        )


async def test_an_unrelated_parent_is_refused(http, school, db, org):
    """A DIFFERENT family's parent, who has a child of their own.

    Distinct from the test above: that one is a parent with no link to the
    pupil at all, this one is a legitimate parent of somebody else, which is
    the realistic shape of the attack. Both must be refused, and for the same
    reason -- the ownership check, not the absence of a scope.
    """
    other_parent = await _preset_user(db, org, "parent")
    db.add(ParentGuardian(user_id=other_parent.id, student_id=school["other"].id,
                          relationship_type="parent", is_primary=True, org_id=org.id))
    await db.commit()

    # Their own child: fine.
    own = await http.get(_card_url(school["other"].id), params={"term": TERM_NAME},
                         headers=_bearer(other_parent))
    assert own.status_code != 403, (
        f"a parent was refused their OWN child: {own.text[:200]}")

    # Musa, who is not theirs: refused.
    r = await http.get(_card_url(school["musa"].id), params={"term": TERM_NAME},
                       headers=_bearer(other_parent))
    assert r.status_code in (403, 404), (
        f"a parent of another child read Musa's card: {r.status_code} {r.text[:200]}"
    )


async def test_the_staff_scope_is_still_not_granted_to_parents(http, school):
    """The exposure this whole arc closed, re-asserted on the fixed code.

    Widening the card route must not have re-opened the class-wide one. If a
    parent can call /report-cards-bulk again, the fix traded one bug for the
    worse one it replaced.
    """
    parent = school["parent"]
    assert not parent.has_permission("school:reports:read"), (
        "the staff report scope has been re-granted to parents")
    assert parent.has_permission("school:reports:own:read")

    r = await http.get("/api/v1/platform/report-cards-bulk",
                       params={"class_id": school["class"].id, "term_id": school["term"].id,
                               "sub_term_id": "s"},
                       headers=_bearer(parent))
    assert r.status_code == 403, (
        f"/report-cards-bulk answered a parent with {r.status_code} -- this "
        f"endpoint returns a WHOLE CLASS's cards and has no ownership check"
    )
