"""The report-config bootstrap must not depend on a section's NAME.

~~~ THE BUG ~~~
`ensure_section` found an existing section with
`existing_secs[name.casefold()]`. Rename the "Primary" row to "Junior" -- which
is what Educare calls it, and what the sidebar displays since phase A -- and the
next run of `report-config/bootstrap` finds no "Primary", creates a SECOND
section, and that endpoint's own guard spells out the result: two sections make
"the report card resolve between them arbitrarily, which can change every
pupil's grade."

This is the test that makes the rename safe. `test_renaming_primary_to_junior_
creates_no_duplicate` is the whole phase; everything else protects the way it
gets there.

~~~ WHY THE EVIDENCE IS THE CLASSES ~~~
Measured against the production dump at head 138: Primary and Secondary both
hold `level_aliases = NULL` -- only Early Years has them. So an alias-based
identity would fail for the exact pair that needs it. Their twelve classes each
DO carry levels (Year 1..Year 6 and Year 7..Year 12), and that is what
identifies them.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.modules.platform import GradingScale, SchoolSection
from app.models.modules.school import SchoolClass
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import bootstrap_report_config

pytestmark = pytest.mark.asyncio

PRIMARY_LEVELS = ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6"]
SECONDARY_LEVELS = ["Year 7", "Year 8", "Year 9", "Year 10", "Year 11", "Year 12"]
EYFS_LEVELS = ["Playgroup", "Pre-Nursery", "Nursery", "Reception"]


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com",
             full_name="Officer", status=UserStatus.ACTIVE, org_id=org.id)
    r = Role(id=str(uuid.uuid4()), name="admin", slug="super_user",
             permissions=["*"], org_id=org.id, is_system=False)
    db.add(r)
    u.roles = [r]
    db.add(u)
    await db.commit()
    return u


async def _section(db, org, name, curriculum, position, aliases=None):
    s = SchoolSection(id=str(uuid.uuid4()), name=name, curriculum=curriculum,
                      position=position, level_aliases=aliases, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _classes(db, org, section, levels):
    """Two classes per level, as production has."""
    for lv in levels:
        for arm in ("A", "B"):
            db.add(SchoolClass(id=str(uuid.uuid4()), name=f"{lv} {arm}", level=lv,
                               section_id=section.id, org_id=org.id))
    await db.commit()


async def _fairview(db, org):
    """Production's shape at head 138: three sections, aliases NULL on the two
    that matter, and every class assigned."""
    ey = await _section(db, org, "Early Years", "eyfs", 0, EYFS_LEVELS)
    pr = await _section(db, org, "Primary", "nigerian", 1, None)
    se = await _section(db, org, "Secondary", "nigerian", 3, None)
    await _classes(db, org, pr, PRIMARY_LEVELS)
    await _classes(db, org, se, SECONDARY_LEVELS)
    await _classes(db, org, ey, EYFS_LEVELS)
    return ey, pr, se


async def _sections(db, org):
    return (await db.execute(select(SchoolSection).where(
        SchoolSection.org_id == org.id).order_by(SchoolSection.position))).scalars().all()


# ── the phase, in one test ──────────────────────────────────────────────────

async def test_renaming_primary_to_junior_creates_no_duplicate(db, org):
    """THE POINT OF PHASE A-PRIME.

    Rename the row, re-run the bootstrap, and there must still be three
    sections -- with the rename intact. Before this change the run created a
    fourth section called "Primary", and the report card then resolved between
    two Primary sections arbitrarily.
    """
    admin = await _admin(db, org)
    ey, pr, se = await _fairview(db, org)

    pr.name = "Junior"                      # what Educare calls it
    db.add(pr)
    await db.commit()

    await bootstrap_report_config(db=db, current_user=admin)

    names = [s.name for s in await _sections(db, org)]
    assert len(names) == 3, (
        f"expected 3 sections, got {len(names)}: {names}. A duplicate here is "
        f"the bug -- two sections for one school and the card picks arbitrarily"
    )
    assert "Junior" in names, "the rename must survive the bootstrap"
    assert names.count("Primary") == 0, "no second Primary may be created"


async def test_renaming_all_three_creates_no_duplicates(db, org):
    """The generalisation: none of the three is identified by its name."""
    admin = await _admin(db, org)
    ey, pr, se = await _fairview(db, org)
    ey.name, pr.name, se.name = "Nursery", "Junior", "Senior School"
    db.add_all([ey, pr, se])
    await db.commit()

    await bootstrap_report_config(db=db, current_user=admin)

    names = sorted(s.name for s in await _sections(db, org))
    assert names == ["Junior", "Nursery", "Senior School"], names


# ── how each one is recognised ──────────────────────────────────────────────

async def test_eyfs_is_recognised_by_curriculum(db, org):
    """Not by name -- the convention `seed_domains` already uses. The section is
    called "Foundation Stage" here and must still be matched."""
    admin = await _admin(db, org)
    ey = await _section(db, org, "Foundation Stage", "eyfs", 0, None)
    pr = await _section(db, org, "Primary", "nigerian", 1, None)
    se = await _section(db, org, "Secondary", "nigerian", 2, None)
    await _classes(db, org, pr, PRIMARY_LEVELS)
    await _classes(db, org, se, SECONDARY_LEVELS)

    await bootstrap_report_config(db=db, current_user=admin)

    secs = await _sections(db, org)
    assert len(secs) == 3, [s.name for s in secs]
    eyfs = [s for s in secs if (s.curriculum or "").lower() == "eyfs"]
    assert len(eyfs) == 1 and eyfs[0].name == "Foundation Stage"


async def test_the_pair_is_told_apart_by_their_classes_year_groups(db, org):
    """Production holds `level_aliases = NULL` on both, and the same
    `curriculum` on both, and positions that do not match what the bootstrap
    passes. The classes are the only evidence, and they are enough."""
    admin = await _admin(db, org)
    pr = await _section(db, org, "Lower School", "nigerian", 5, None)
    se = await _section(db, org, "Upper School", "nigerian", 6, None)
    await _classes(db, org, pr, PRIMARY_LEVELS)
    await _classes(db, org, se, SECONDARY_LEVELS)
    assert pr.level_aliases is None and se.level_aliases is None

    await bootstrap_report_config(db=db, current_user=admin)

    secs = await _sections(db, org)
    # Early Years is created (none existed); the two existing ones are REUSED.
    assert sorted(s.name for s in secs) == ["Early Years", "Lower School", "Upper School"]


async def test_class_level_matching_folds_case_and_whitespace(db, org):
    """Classes hold 'Year 7'; the bootstrap passes 'YEAR 7'. A case-sensitive
    comparison matches neither way round -- the same trap as the year-group
    filter in phase B."""
    admin = await _admin(db, org)
    pr = await _section(db, org, "Lower", "nigerian", 1, None)
    se = await _section(db, org, "Upper", "nigerian", 2, None)
    await _classes(db, org, pr, ["year 1", "  Year 2  ", "YEAR 3"])
    await _classes(db, org, se, ["Year 7", "year 8"])

    await bootstrap_report_config(db=db, current_user=admin)

    assert sorted(s.name for s in await _sections(db, org)) == \
        ["Early Years", "Lower", "Upper"]


async def test_stored_aliases_are_used_when_there_are_no_classes(db, org):
    """An org that populated `level_aliases` but has not created classes yet
    still resolves -- step 3 of the order."""
    admin = await _admin(db, org)
    await _section(db, org, "Junior", "nigerian", 1, PRIMARY_LEVELS)
    await _section(db, org, "Senior", "nigerian", 2, SECONDARY_LEVELS)

    await bootstrap_report_config(db=db, current_user=admin)

    assert sorted(s.name for s in await _sections(db, org)) == \
        ["Early Years", "Junior", "Senior"]


# ── the behaviour that must not regress ─────────────────────────────────────

async def test_first_run_on_an_empty_org_creates_the_three(db, org):
    admin = await _admin(db, org)
    await bootstrap_report_config(db=db, current_user=admin)
    assert sorted(s.name for s in await _sections(db, org)) == \
        ["Early Years", "Primary", "Secondary"]


async def test_running_twice_is_idempotent(db, org):
    """The documented self-healing behaviour. Two runs, three sections."""
    admin = await _admin(db, org)
    await bootstrap_report_config(db=db, current_user=admin)
    first = [s.id for s in await _sections(db, org)]
    await bootstrap_report_config(db=db, current_user=admin)
    second = [s.id for s in await _sections(db, org)]
    assert len(second) == 3
    assert sorted(first) == sorted(second), "the same rows must be reused, not replaced"


async def test_a_bare_unnamed_match_still_works_by_name(db, org):
    """Step 4, the fallback. A section with no classes and no aliases is only
    identifiable by its name, and that must keep working."""
    admin = await _admin(db, org)
    await _section(db, org, "Primary", "nigerian", 1, None)

    await bootstrap_report_config(db=db, current_user=admin)

    secs = await _sections(db, org)
    assert sorted(s.name for s in secs) == ["Early Years", "Primary", "Secondary"]
    assert len(secs) == 3, "the bare Primary must be reused, not duplicated"


async def test_aliases_are_backfilled_onto_a_bare_section(db, org):
    """Pre-existing behaviour, asserted so the new resolver does not lose it."""
    admin = await _admin(db, org)
    pr = await _section(db, org, "Primary", "nigerian", 1, None)
    await bootstrap_report_config(db=db, current_user=admin)
    await db.refresh(pr)
    assert pr.level_aliases, "a bare section should gain the alias list"


async def test_a_tie_is_not_guessed(db, org):
    """Two sections with IDENTICAL class levels cannot be told apart. The
    resolver must fall through to the name rather than pick one, because
    picking is the arbitrary resolution the guard exists to prevent."""
    admin = await _admin(db, org)
    a = await _section(db, org, "Primary", "nigerian", 1, None)
    b = await _section(db, org, "Duplicate", "nigerian", 2, None)
    await _classes(db, org, a, PRIMARY_LEVELS)
    await _classes(db, org, b, PRIMARY_LEVELS)       # the same evidence

    await bootstrap_report_config(db=db, current_user=admin)

    names = sorted(s.name for s in await _sections(db, org))
    # "Primary" matched by NAME, so no third nigerian section appeared.
    assert "Primary" in names and "Duplicate" in names
    assert names.count("Primary") == 1


async def test_the_foreign_grading_scale_guard_still_fires(db, org):
    """The endpoint refuses to run at all when the org has a grading scale it
    did not create. Asserted here because this phase edits the lines directly
    above that guard."""
    from fastapi import HTTPException

    admin = await _admin(db, org)
    db.add(GradingScale(id=str(uuid.uuid4()), name="Someone Else's Scale",
                        scale_type="numeric", purpose="grade",
                        is_provisional=False, org_id=org.id))
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await bootstrap_report_config(db=db, current_user=admin)
    assert exc.value.status_code == 409


# ── A-prime-prime pre-flight: renaming the CLASSES must change nothing ──────
#
# A'' renames all 31 demo classes to Educare's real names and clears the arm
# (`school_classes.section`), while deliberately LEAVING `level` and
# `section_id` alone. These tests pin why that distinction matters, before the
# rename is written.

#: Educare-style names, invented for this test -- the real list has not arrived.
#: Deliberately unlike the current ones: a word arm instead of A/B, and nothing
#: that contains the class's own `level` string.
EDUCARE_STYLE = {
    "Year 1 A": "YEAR 1 COPPER",   "Year 1 B": "YEAR 1 BRONZE",
    "Year 2 A": "YEAR 2 CORAL",    "Year 2 B": "YEAR 2 AMBER",
    "Year 3 A": "YEAR 3 IVORY",    "Year 3 B": "YEAR 3 INDIGO",
    "Year 4 A": "YEAR 4 TOPAZ",    "Year 4 B": "YEAR 4 ONYX",
    "Year 5 A": "YEAR 5 GARNET",   "Year 5 B": "YEAR 5 OPAL",
    "Year 6 A": "YEAR 6 PEARL",    "Year 6 B": "YEAR 6 RUBY",
    "Year 7 A": "YEAR 7 AMETHYST", "Year 7 B": "YEAR 7 MOONLIGHT",
    "Year 8 A": "YEAR 8 JADE",     "Year 8 B": "YEAR 8 QUARTZ",
    "Year 9 A": "YEAR 9 SLATE",    "Year 9 B": "YEAR 9 COBALT",
    "Year 10 A": "YEAR 10 AMETHYST", "Year 10 B": "YEAR 10 MOONLIGHT",
    "Year 11 A": "YEAR 11 JADE",   "Year 11 B": "YEAR 11 FLINT",
    "Year 12 A": "YEAR 12 OBSIDIAN", "Year 12 B": "YEAR 12 BASALT",
    "Playgroup A": "PLAYGROUP SUNFLOWERS", "Playgroup B": "PLAYGROUP DAISIES",
    "Pre-Nursery A": "PRE-NURSERY LILAC", "Pre-Nursery B": "PRE-NURSERY LILLIES",
    "Nursery A": "NURSERY BLOSSOM", "Nursery B": "NURSERY MAPLES",
    "Reception A": "RECEPTION OLIVES", "Reception B": "RECEPTION TULIP",
}


async def _class_map(db, org):
    """{class id: (name, level, section_id, arm)} for the whole org."""
    rows = (await db.execute(select(SchoolClass).where(
        SchoolClass.org_id == org.id))).scalars().all()
    return {c.id: (c.name, c.level, c.section_id, c.section) for c in rows}


async def test_renaming_every_class_leaves_sections_and_assignments_intact(db, org):
    """THE A'' PRE-FLIGHT.

    Rename all the classes to Educare-style names and clear the arm -- exactly
    what A'' will do -- then re-run the bootstrap. Nothing about the sections or
    the class-to-section assignments may move.

    This holds because identity is resolved from `school_classes.level`, which
    the rename does NOT touch. That is the whole reason the rename plan leaves
    `level` alone, and this test is what makes that constraint enforceable
    rather than a note in a commit message.
    """
    admin = await _admin(db, org)
    ey, pr, se = await _fairview(db, org)
    # Early Years classes in `_fairview` are named "<level> A"/"<level> B", so
    # the whole roster is covered by the rename map.
    before = await _class_map(db, org)
    section_ids_before = sorted(s.id for s in await _sections(db, org))

    renamed = 0
    for cid, (name, level, sec_id, arm) in before.items():
        new = EDUCARE_STYLE.get(name)
        if not new:
            continue
        c = await db.get(SchoolClass, cid)
        c.name = new
        c.section = None          # A'' clears the arm: Educare's names carry it
        db.add(c)
        renamed += 1
    await db.commit()
    assert renamed == len(before), (
        f"the rename map covered {renamed} of {len(before)} classes -- extend "
        f"EDUCARE_STYLE so the test exercises the whole roster")

    await bootstrap_report_config(db=db, current_user=admin)

    # 1. the same three sections, by ID -- none created, none replaced
    assert sorted(s.id for s in await _sections(db, org)) == section_ids_before

    # 2. every class still sits in the section it sat in, with its level intact
    after = await _class_map(db, org)
    assert set(after) == set(before), "no class may be created or removed"
    for cid, (name, level, sec_id, arm) in after.items():
        old_name, old_level, old_sec, _old_arm = before[cid]
        assert sec_id == old_sec, f"{name}: section_id moved"
        assert level == old_level, f"{name}: level changed -- A'' must not touch it"
        assert name == EDUCARE_STYLE[old_name], f"{old_name}: rename did not stick"
        assert arm is None, f"{name}: the arm should have been cleared"


async def test_the_rename_is_idempotent_across_two_bootstrap_runs(db, org):
    """A'' runs once, but the bootstrap may run again afterwards at any time."""
    admin = await _admin(db, org)
    ey, pr, se = await _fairview(db, org)
    for cid, (name, *_rest) in (await _class_map(db, org)).items():
        if name in EDUCARE_STYLE:
            c = await db.get(SchoolClass, cid)
            c.name = EDUCARE_STYLE[name]
            db.add(c)
    await db.commit()

    await bootstrap_report_config(db=db, current_user=admin)
    once = sorted(s.id for s in await _sections(db, org))
    await bootstrap_report_config(db=db, current_user=admin)
    twice = sorted(s.id for s in await _sections(db, org))
    assert once == twice and len(twice) == 3


async def test_changing_level_as_well_IS_what_breaks_it(db, org):
    """The negative case, which is why the rename plan says to leave `level`.

    Renaming the classes is safe. Renaming their LEVELS destroys the evidence
    the resolver uses, and the bootstrap then cannot recognise the sections --
    it falls back to the name, and with the sections also renamed it would
    create new ones. Asserted so nobody "tidies" level into the rename.
    """
    admin = await _admin(db, org)
    ey, pr, se = await _fairview(db, org)

    # the rename plan's forbidden move: level changed too, and sections renamed
    for cid, (name, level, sec_id, arm) in (await _class_map(db, org)).items():
        c = await db.get(SchoolClass, cid)
        c.level = f"Form {level}"          # no longer matches any alias
        db.add(c)
    pr.name, se.name = "Junior", "Senior School"
    db.add_all([pr, se])
    await db.commit()

    await bootstrap_report_config(db=db, current_user=admin)

    names = sorted(s.name for s in await _sections(db, org))
    assert len(names) > 3, (
        "with `level` destroyed AND the sections renamed, the bootstrap can no "
        "longer recognise them -- this is the duplicate-section outcome A'' "
        "must avoid, and the reason `level` is out of scope for the rename. "
        f"got {names}")
