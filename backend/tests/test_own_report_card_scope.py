"""What the parent/pupil Report Cards view is allowed to reach.

The frontend's OwnReportCardsView trusts two things:

    GET /school/students                           -> only MY pupils (child picker)
    GET /school/students/{student_id}/report-card  -> refused for anyone else

test_parent_card_page_flow.py proves the page LOADS for a parent and that an
unlinked child's card is refused. It does not assert what the picker list
contains -- only that it is not a 403 -- and it never has a pupil ask for
another pupil. A list that leaked the whole class would pass it, and the child
selector would then offer every pupil in the school. This file pins both.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.modules.school import ParentGuardian, Student
from tests.test_parent_card_page_flow import (  # noqa: F401  (fixtures)
    TERM_NAME, _bearer, _card_url, _preset_user, http, school,
)

pytestmark = pytest.mark.asyncio

STUDENTS = "/api/v1/school/students"


async def _listed_ids(http, user) -> set[str]:
    r = await http.get(STUDENTS, headers=_bearer(user))
    assert r.status_code == 200, f"the child picker's list was refused: {r.text[:200]}"
    return {row["id"] for row in r.json()["items"]}


async def _sibling(db, org, school) -> Student:
    """A second child of the same parent, in the same class as `other`."""
    sib = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}",
                  first_name="Amina", last_name="Yusuf", class_id=school["class"].id,
                  org_id=org.id)
    db.add(sib)
    await db.flush()
    db.add(ParentGuardian(user_id=school["parent"].id, student_id=sib.id,
                          relationship_type="parent", is_primary=True, org_id=org.id))
    await db.commit()
    return sib


# -- the picker list ---------------------------------------------------------

async def test_a_parent_lists_exactly_their_linked_children(http, school, db, org):
    sib = await _sibling(db, org, school)

    ids = await _listed_ids(http, school["parent"])

    assert ids == {school["musa"].id, sib.id}, (
        f"a parent's picker should hold their two children and nobody else; "
        f"got {len(ids)} rows, other family's child present: {school['other'].id in ids}"
    )


async def test_a_pupil_lists_only_themselves(http, school):
    ids = await _listed_ids(http, school["pupil_user"])
    assert ids == {school["musa"].id}


async def test_a_parent_with_no_links_lists_nobody(http, school, db, org):
    """list_students refuses a caller who is neither staff nor linked to anyone
    (403), rather than answering with an empty list. Either is safe; what must
    never happen is a row coming back."""
    stranger = await _preset_user(db, org, "parent")
    r = await http.get(STUDENTS, headers=_bearer(stranger))
    assert r.status_code in (200, 403), f"{r.status_code} {r.text[:200]}"
    if r.status_code == 200:
        assert r.json()["items"] == [], "an unlinked parent was handed pupils"


# -- the card ----------------------------------------------------------------

async def test_a_parent_reaches_each_linked_child_card(http, school, db, org):
    sib = await _sibling(db, org, school)
    for child in (school["musa"], sib):
        r = await http.get(_card_url(child.id), params={"term": TERM_NAME},
                           headers=_bearer(school["parent"]))
        assert r.status_code == 200, f"{child.first_name}: {r.status_code} {r.text[:200]}"


async def test_a_pupil_cannot_load_a_classmates_card(http, school):
    r = await http.get(_card_url(school["other"].id), params={"term": TERM_NAME},
                       headers=_bearer(school["pupil_user"]))
    assert r.status_code in (403, 404), (
        f"a pupil loaded a classmate's card: {r.status_code} {r.text[:200]}"
    )


async def test_a_parent_with_no_links_cannot_load_any_card(http, school, db, org):
    stranger = await _preset_user(db, org, "parent")
    for student_id in (school["musa"].id, school["other"].id):
        r = await http.get(_card_url(student_id), params={"term": TERM_NAME},
                           headers=_bearer(stranger))
        assert r.status_code in (403, 404), f"{r.status_code} {r.text[:200]}"


async def test_an_unknown_student_id_is_refused(http, school):
    r = await http.get(_card_url(str(uuid.uuid4())), params={"term": TERM_NAME},
                       headers=_bearer(school["parent"]))
    assert r.status_code in (403, 404), f"{r.status_code} {r.text[:200]}"
