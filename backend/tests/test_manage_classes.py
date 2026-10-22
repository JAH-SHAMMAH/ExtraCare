"""Manage Class / Manage YearGroups: school filter, year-group filter, ordering, category."""
from __future__ import annotations

import pytest

from app.models.modules.platform import SchoolSection
from app.models.modules.school import SchoolClass, YearGroup
from app.routers.modules.school import (
    list_classes, list_year_groups, create_class, create_year_group, reorder_year_groups,
)
from app.schemas.school_class import ClassCreate
from app.schemas.year_group import YearGroupCreate, ReorderRequest

pytestmark = pytest.mark.asyncio


async def _world(db, org):
    early = SchoolSection(name="Early Years", curriculum="eyfs", position=0, org_id=org.id)
    sec = SchoolSection(name="Secondary", curriculum="hybrid", position=2, org_id=org.id)
    db.add_all([early, sec]); await db.flush()
    y7 = YearGroup(name="Year 7", category="active", position=2, section_id=sec.id, org_id=org.id)
    y8 = YearGroup(name="Year 8", category="active", position=3, section_id=sec.id, org_id=org.id)
    alu = YearGroup(name="Alumni", category="alumni", position=9, section_id=sec.id, org_id=org.id)
    pg = YearGroup(name="Play Group", category="active", position=0, section_id=early.id, org_id=org.id)
    db.add_all([y7, y8, alu, pg]); await db.flush()
    for name, level, s in [("Year 8 Garnet", "Year 8", sec), ("Year 7 Coral", "Year 7", sec),
                           ("2024/2025 Alumni", "Alumni", sec), ("Playgroup", "Play Group", early)]:
        db.add(SchoolClass(name=name, level=level, section_id=s.id, org_id=org.id))
    await db.flush()
    return early, sec


async def test_filters_order_and_category(db, org, teacher):
    early, sec = await _world(db, org)
    got = await list_classes(page=1, page_size=100, search=None, section_id=sec.id, year_group=None, db=db, current_user=teacher)
    assert [c["name"] for c in got["items"]] == ["Year 7 Coral", "Year 8 Garnet", "2024/2025 Alumni"]  # year-group order
    assert got["items"][2]["category"] == "alumni"
    assert got["items"][0]["year_group"] == "Year 7"
    one = await list_classes(page=1, page_size=100, search=None, section_id=sec.id, year_group="year 8", db=db, current_user=teacher)
    assert [c["name"] for c in one["items"]] == ["Year 8 Garnet"]
    ey = await list_classes(page=1, page_size=100, search=None, section_id=early.id, year_group=None, db=db, current_user=teacher)
    assert [c["name"] for c in ey["items"]] == ["Playgroup"]


async def test_year_groups_by_school_and_reorder_keeps_others(db, org, teacher):
    early, sec = await _world(db, org)
    only = await list_year_groups(section_id=sec.id, db=db, current_user=teacher)
    assert [y["name"] for y in only] == ["Year 7", "Year 8", "Alumni"]
    ids = [only[1]["id"], only[0]["id"], only[2]["id"]]   # swap Year 7 / Year 8
    out = await reorder_year_groups(ReorderRequest(ids=ids), db=db, current_user=teacher)
    assert [y["name"] for y in out if y["section_id"] == sec.id] == ["Year 8", "Year 7", "Alumni"]
    assert next(y for y in out if y["name"] == "Play Group")["position"] == 0   # other school untouched


async def test_create_in_a_school(db, org, teacher):
    early, sec = await _world(db, org)
    yg = await create_year_group(YearGroupCreate(name="Year 9", short_code="Y9", section_id=sec.id), db=db, current_user=teacher)
    assert yg["section_id"] == sec.id
    c = await create_class(ClassCreate(name="Year 9 Peridot", grade_level="Year 9", section_id=sec.id), db=db, current_user=teacher)
    assert c["year_group"] == "Year 9" and c["section_id"] == sec.id


# ── optional assistant teacher ──────────────────────────────────────────────

async def test_assistant_is_optional_and_shown(db, org, teacher):
    from app.routers.modules.school import update_class
    from app.schemas.school_class import ClassUpdate
    _early, sec = await _world(db, org)
    plain = await create_class(ClassCreate(name="Year 9 Peridot", grade_level="Year 9", section_id=sec.id), db=db, current_user=teacher)
    assert plain["assistant_teacher_id"] is None and plain["pc_teachers"] == []   # no assistant needed
    from app.models.user import User
    other = User(email="asst@x.com", hashed_password="x", full_name="Asst One", org_id=org.id)
    db.add(other); await db.flush()
    c = await update_class(plain["id"], ClassUpdate(class_teacher_id=teacher.id, assistant_teacher_id=other.id), db=db, current_user=teacher)
    assert [p["role"] for p in c["pc_teachers"]] == ["class_teacher", "assistant"]
    cleared = await update_class(plain["id"], ClassUpdate(assistant_teacher_id=""), db=db, current_user=teacher)
    assert cleared["assistant_teacher_id"] is None and len(cleared["pc_teachers"]) == 1


async def test_assistant_cannot_equal_class_teacher(db, org, teacher):
    from fastapi import HTTPException
    from app.routers.modules.school import update_class
    from app.schemas.school_class import ClassUpdate
    _e, sec = await _world(db, org)
    c = await create_class(ClassCreate(name="Year 9 Peridot", section_id=sec.id, class_teacher_id=teacher.id), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as e:
        await update_class(c["id"], ClassUpdate(assistant_teacher_id=teacher.id), db=db, current_user=teacher)
    assert e.value.status_code == 422


async def test_assistant_can_comment_but_not_submit_or_open_results(db, org, teacher):
    from fastapi import HTTPException
    from app.models.user import User
    from app.routers.modules.platform import _gate_comment_access, _class_for_reports_or_403
    from app.routers.modules.school import update_class
    from app.schemas.school_class import ClassUpdate
    _e, sec = await _world(db, org)
    asst = User(email="asst2@x.com", hashed_password="x", full_name="Asst Two", org_id=org.id)
    db.add(asst); await db.flush(); await db.refresh(asst, ["roles"])
    c = await create_class(ClassCreate(name="Year 9 Peridot", section_id=sec.id, class_teacher_id=teacher.id), db=db, current_user=teacher)
    # Not an assistant yet: refused.
    with pytest.raises(HTTPException):
        await _gate_comment_access(db, org.id, asst, c["id"], "pc")
    await update_class(c["id"], ClassUpdate(assistant_teacher_id=asst.id), db=db, current_user=teacher)
    await _gate_comment_access(db, org.id, asst, c["id"], "pc")          # now allowed
    with pytest.raises(HTTPException):                                      # still not the class teacher
        await _class_for_reports_or_403(db, org.id, asst, c["id"])
