"""Tests for the Educare-parity role catalogue: the new presets exist with the
right permission tiers + display names, and the per-org role sync seeds them."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import (
    SCHOOL_PERMISSION_PRESETS, role_display_name, Role,
)
from app.routers.organizations import sync_roles_for_current_org


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


def test_new_presets_exist_with_expected_tiers():
    p = SCHOOL_PERMISSION_PRESETS
    # Leadership → full admin.
    assert p["principal"] == p["org_admin"] and p["super_user"] == p["org_admin"]
    # Senior admin → manager tier.
    assert p["vice_principal"] == p["manager"] and p["head_of_administration"] == p["manager"]
    # Academic → teacher tier (incl. Sports/PE officer).
    assert p["academic_coordinator"] == p["teacher"] and p["spa_officer"] == p["teacher"]
    # Exam/Admission Officer + Guidance Counsellor are NARROW (no broad school:write).
    assert "school:write" not in p["exam_officer"] and "school:read" not in p["exam_officer"]
    assert set(p["exam_officer"]) >= {"school:exams:read", "school:exams:write", "school:students:read", "school:subjects:read", "school:classes:read"}
    assert set(p["admission_officer"]) == {"school:admissions:read", "school:admissions:write", "school:students:read", "users:read", "hr:read"}
    assert set(p["guidance_counsellor"]) >= {"school:behaviour:read", "school:behaviour:write", "school:feedback:read", "school:feedback:write"}
    assert "school:write" not in p["guidance_counsellor"]
    # Specialist → narrow scopes.
    assert set(p["hr_manager"]) >= {"hr:read", "hr:write", "users:read"}
    assert set(p["librarian"]) >= {"school:library:read", "school:library:write"}
    assert "medical:read" in p["school_nurse"]
    # Support staff → self-service only.
    for slug in ("janitor", "driver", "kitchen_assistant", "spa_attendant", "caregiver"):
        assert p[slug] == ["hr:read"]
    # All 37 Educare roles resolvable (spot the total is well beyond the old 11).
    assert len(p) >= 40


def test_display_name_overrides():
    assert role_display_name("hr_manager") == "HR Manager"
    assert role_display_name("spa_officer") == "SPA Officer"
    assert role_display_name("frontdesk_officer") == "FrontDesk Officer"
    assert role_display_name("head_of_department_secondary") == "Head of Department (Secondary)"
    assert role_display_name("vice_principal") == "Vice Principal"     # plain title-case path


async def test_sync_seeds_new_roles_into_existing_org(db, org):
    admin = await _admin(db, org)
    # Fresh fixture org has no seeded roles.
    before = (await db.execute(select(Role).where(Role.org_id == org.id, Role.is_system == True))).scalars().all()  # noqa: E712
    assert len(before) == 0

    res = await sync_roles_for_current_org(db=db, current_user=admin)
    assert res["synced"] is True and res["system_roles"] >= 40

    roles = {r.slug: r for r in (await db.execute(select(Role).where(Role.org_id == org.id))).scalars().all()}
    assert "vice_principal" in roles and roles["vice_principal"].name == "Vice Principal"
    assert roles["hr_manager"].name == "HR Manager"
    assert roles["janitor"].permissions == ["hr:read"]

    # Idempotent — a second sync creates no duplicates.
    await sync_roles_for_current_org(db=db, current_user=admin)
    again = (await db.execute(select(Role).where(Role.org_id == org.id, Role.slug == "vice_principal"))).scalars().all()
    assert len(again) == 1
