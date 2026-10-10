"""The sidebar's report-section mapping, and the lockout it replaces.

THE FAILURE BEING GUARDED. The browser decided which report section a teacher
could see by comparing her section's NAME to the literal "Nursery". Fairview's
EYFS section is named "Early Years", so an Early Years teacher matched nothing
and the Nursery report section was hidden from her entirely — while every page
inside it answered her perfectly well by URL. Permission tests all passed; the
feature was simply unfindable.

Every test here is written so that it would fail if a name comparison came back.
`test_the_eyfs_section_is_not_called_nursery_and_still_resolves` is the bug
itself; `test_renaming_sections_changes_nothing` is the generalisation.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.services.report_sections import (
    JUNIOR, NURSERY, REPORT_KEYS, SECONDARY, report_keys_for,
)


@dataclass
class Sec:
    """Stand-in for a SchoolSection row: the function reads only these four.

    A plain object rather than the model, so these stay pure unit tests — the
    mapping rule is arithmetic on a list and deserves to be tested as such.
    """
    name: str
    curriculum: str
    position: int
    id: str = ""

    def __post_init__(self):
        self.id = self.id or f"id-{self.name.lower().replace(' ', '-')}"


#: Fairview's actual three rows, as read out of the production dump at head 138.
FAIRVIEW = [
    Sec("Early Years", "eyfs", 0),
    Sec("Primary", "nigerian", 1),
    Sec("Secondary", "nigerian", 3),
]


# ── the production shape ─────────────────────────────────────────────────────

def test_fairviews_three_sections_map_to_the_three_report_keys():
    keys = report_keys_for(FAIRVIEW)
    assert keys == {
        "id-early-years": NURSERY,
        "id-primary": JUNIOR,
        "id-secondary": SECONDARY,
    }


def test_the_eyfs_section_is_not_called_nursery_and_still_resolves():
    """THE BUG. "Early Years" never equalled "Nursery", so the comparison failed
    and the section vanished from the sidebar. Identity comes from `curriculum`
    — the convention `seed_domains` and the report-config bootstrap already use,
    whose comment reads "EYFS detection keys on curriculum, not name"."""
    eyfs = next(s for s in FAIRVIEW if s.curriculum == "eyfs")
    assert eyfs.name != "Nursery", "precondition: the row is not named Nursery"
    assert report_keys_for(FAIRVIEW)[eyfs.id] == NURSERY


def test_renaming_sections_changes_nothing():
    """The generalisation. Primary and Secondary matched only because their names
    happened to equal the literals; a rename in Report Setup would have hidden
    them the same way. Rename all three to something else and the mapping must be
    byte-identical."""
    renamed = [
        Sec("Nursery", "eyfs", 0, id="id-early-years"),
        Sec("Junior", "nigerian", 1, id="id-primary"),
        Sec("Senior School", "nigerian", 3, id="id-secondary"),
    ]
    assert report_keys_for(renamed) == report_keys_for(FAIRVIEW)


def test_curriculum_match_is_case_insensitive():
    """Bootstrap writes 'eyfs'; a hand-edited row could hold 'EYFS'. The section
    is the same section."""
    assert report_keys_for([
        Sec("Early Years", "EYFS", 0), Sec("P", "nigerian", 1), Sec("S", "nigerian", 2),
    ])["id-early-years"] == NURSERY


def test_curriculum_may_be_hybrid_or_nigerian_for_the_school_sections():
    """`report-config/bootstrap` writes 'hybrid' for Primary/Secondary while
    production holds 'nigerian'. Neither is EYFS, and both must classify the
    same — this disagreement is live and must not matter."""
    hybrid = [Sec("Early Years", "eyfs", 0),
              Sec("Primary", "hybrid", 1), Sec("Secondary", "hybrid", 2)]
    assert report_keys_for(hybrid) == report_keys_for(FAIRVIEW)


# ── junior vs senior is decided by position, not by name or row order ───────

def test_position_decides_junior_and_senior_not_the_name():
    """Names chosen to mislead: alphabetically "Alpha" sorts first, but position
    says it is the senior school."""
    keys = report_keys_for([
        Sec("Alpha", "nigerian", 9), Sec("Zulu", "nigerian", 1),
    ])
    assert keys["id-zulu"] == JUNIOR
    assert keys["id-alpha"] == SECONDARY


def test_row_order_does_not_change_the_answer():
    """A list read back from the database arrives in whatever order the planner
    chose. Reversing the input must not move a single key."""
    assert report_keys_for(list(reversed(FAIRVIEW))) == report_keys_for(FAIRVIEW)


def test_a_position_tie_is_broken_deterministically():
    """Two sections sharing a position must still resolve the same way on every
    call — an arbitrary winner here would make the sidebar's contents depend on
    row order, which is the `.first()` hazard recorded for the grading scales."""
    tied = [Sec("Bravo", "nigerian", 1), Sec("Alpha", "nigerian", 1)]
    first = report_keys_for(tied)
    assert first == report_keys_for(list(reversed(tied)))
    assert first["id-alpha"] == JUNIOR and first["id-bravo"] == SECONDARY


# ── failing open ─────────────────────────────────────────────────────────────

def test_one_non_eyfs_section_is_left_unmapped_so_the_sidebar_fails_open():
    """Junior and senior are RELATIVE; with one school section there is no
    comparison to make. It is returned unmapped, and the sidebar shows every
    report section rather than hiding one — the fault being fixed is a lockout,
    and a resolution gap must not reproduce it."""
    keys = report_keys_for([Sec("Early Years", "eyfs", 0), Sec("The School", "nigerian", 1)])
    assert keys == {"id-early-years": NURSERY}
    assert "id-the-school" not in keys


def test_a_middle_section_is_left_unmapped():
    """Three school sections: the ends classify, the middle is genuinely neither.
    Unmapped, not guessed."""
    keys = report_keys_for([
        Sec("Lower", "nigerian", 1), Sec("Middle", "nigerian", 2), Sec("Upper", "nigerian", 3),
    ])
    assert keys["id-lower"] == JUNIOR
    assert keys["id-upper"] == SECONDARY
    assert "id-middle" not in keys


def test_no_sections_at_all():
    """A fresh org before setup. Empty, not an exception — this runs on every
    login."""
    assert report_keys_for([]) == {}


def test_only_an_eyfs_section():
    assert report_keys_for([Sec("Early Years", "eyfs", 0)]) == {"id-early-years": NURSERY}


def test_every_key_produced_is_one_the_sidebar_knows():
    """A key the manifest does not carry would silently hide a section. Pins the
    vocabulary to the one both sides share."""
    for key in report_keys_for(FAIRVIEW).values():
        assert key in REPORT_KEYS


def test_report_keys_are_ordered_senior_first():
    """Educare lists Secondary, Junior, Nursery. The order lives beside the keys
    so the sidebar and this module cannot disagree about it."""
    assert REPORT_KEYS == (SECONDARY, JUNIOR, NURSERY)


# ── the database-backed resolver used by /auth/login and /auth/me ───────────

pytestmark_db = pytest.mark.asyncio


@pytest_asyncio.fixture
async def three_sections(db, org):
    """Fairview's three rows, in the database."""
    from app.models.modules.platform import SchoolSection

    rows = [
        SchoolSection(id=str(uuid.uuid4()), name="Early Years", curriculum="eyfs",
                      position=0, org_id=org.id),
        SchoolSection(id=str(uuid.uuid4()), name="Primary", curriculum="nigerian",
                      position=1, org_id=org.id),
        SchoolSection(id=str(uuid.uuid4()), name="Secondary", curriculum="nigerian",
                      position=3, org_id=org.id),
    ]
    for r in rows:
        db.add(r)
    await db.commit()
    return {r.name: r for r in rows}


@pytest.mark.asyncio
async def test_resolver_reads_the_whole_org(db, org, three_sections):
    from app.routers.auth import _report_key_map

    keys = await _report_key_map(db, org.id)
    assert keys[three_sections["Early Years"].id] == NURSERY
    assert keys[three_sections["Primary"].id] == JUNIOR
    assert keys[three_sections["Secondary"].id] == SECONDARY


@pytest.mark.asyncio
async def test_resolver_does_not_see_another_orgs_sections(db, org, three_sections):
    """Tenant scoping, asserted because the resolver reads the table unfiltered
    by anything except org — another school's sections would change which of
    THIS school's sections counts as senior."""
    from app.models.organization import Organization
    from app.models.modules.platform import SchoolSection
    from app.routers.auth import _report_key_map

    other = Organization(id=str(uuid.uuid4()), name="Other School", slug=f"other-{uuid.uuid4().hex[:6]}")
    db.add(other)
    await db.commit()
    db.add(SchoolSection(id=str(uuid.uuid4()), name="Sixth Form", curriculum="nigerian",
                         position=99, org_id=other.id))
    await db.commit()

    keys = await _report_key_map(db, org.id)
    assert keys[three_sections["Secondary"].id] == SECONDARY, (
        "another org's higher-positioned section must not take the senior slot"
    )
    assert len(keys) == 3


@pytest.mark.asyncio
async def test_section_brief_carries_the_report_key(db, org, three_sections):
    """The field the sidebar actually reads. Defaults to None so an older caller
    constructing a brief without it still validates."""
    from app.schemas.auth import SectionBrief

    assert SectionBrief(id="x", name="y").report_key is None
    brief = SectionBrief(id=three_sections["Early Years"].id, name="Early Years",
                         report_key=NURSERY)
    assert brief.report_key == NURSERY
