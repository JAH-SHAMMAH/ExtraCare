"""The ICT Support role, and the two properties that make it safe.

`it_support` exists to run a helpdesk: create accounts, assign roles, reset
forgotten passwords. Because `assert_can_manage_user` lets you manage a user only
when you hold every permission their roles carry, the role has to COVER the
everyday tiers to be useful at all — a users:*/roles:* -only role cannot reset an
ordinary teacher's password.

That makes the scope list wide, so two properties are asserted here rather than
left to inspection, and both must hold for any future scope change:

  REACH  — ICT can manage the everyday roles it exists to support.
  LIMIT  — no role ICT can manage carries a privilege-escalating or money-moving
           scope, and the protected tiers stay unreachable.

The second is the one that matters. If a future edit widens ICT far enough to
cover, say, hr_manager, ICT could reset that account's password, log in, and use
its `users:write` — so LIMIT is expressed against the sensitive SCOPES, not
against a hand-listed set of role names that someone could forget to update.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.permissions import _uncovered_perms
from app.models.role import SCHOOL_PERMISSION_PRESETS, Role
from app.models.user import User, UserStatus
from app.routers.users import reset_user_password, update_user_status
from app.schemas.user import UserStatusUpdate

# No module-level asyncio marker: pytest.ini sets `asyncio_mode = auto`, and this
# file mixes sync scope-math tests with async handler tests — marking the sync
# ones would only emit warnings.


# Everyday roles the helpdesk must be able to serve.
SUPPORTED = [
    "teacher", "instructor", "student", "parent", "staff", "viewer", "librarian",
    "frontdesk_officer", "storekeeper", "caregiver", "driver", "janitor",
    "kitchen_assistant", "head_teacher", "academic_coordinator", "exam_officer",
]

# Tiers that must stay unreachable: they escalate privilege, move money, or read
# confidential HR records.
PROTECTED = [
    "super_user", "org_admin", "principal", "head", "vice_principal",
    "deputy_head", "head_of_administration", "administrative_coordinator",
    "manager", "hr_manager", "accountant",
]

# Holding any of these means an account can escalate privilege or move money.
SENSITIVE_SCOPES = [
    "*", "users:write", "users:delete", "roles:read", "roles:write",
    "finance_admin:read", "finance_admin:write", "payments:write", "payments:post",
    "settings:write", "audit_logs:read", "hr:write", "imports:write", "imports:rollback",
]


def _stub(slug: str) -> User:
    """An in-memory user carrying `slug`'s preset — no DB needed for scope math."""
    u = User(id=slug, email=f"{slug}@x", full_name=slug, org_id="o")
    u.roles = [Role(id=slug, name=slug, slug=slug,
                    permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id="o")]
    return u


def _can_manage(actor: User, target: User) -> bool:
    return all(not _uncovered_perms(actor, r) for r in (target.roles or []))


# ── the two properties ────────────────────────────────────────────────────────

def test_role_exists_and_carries_the_account_management_scopes():
    perms = set(SCHOOL_PERMISSION_PRESETS["it_support"])
    assert {"users:read", "users:write", "roles:read", "roles:write"} <= perms


@pytest.mark.parametrize("slug", SUPPORTED)
def test_reach_ict_can_manage_everyday_roles(slug):
    """Without this the helpdesk role cannot do its job."""
    missing = _uncovered_perms(_stub("it_support"), _stub(slug).roles[0])
    assert not missing, f"it_support cannot manage {slug}; missing {missing}"


@pytest.mark.parametrize("slug", PROTECTED)
def test_limit_protected_tiers_stay_unreachable(slug):
    assert not _can_manage(_stub("it_support"), _stub(slug)), \
        f"it_support must not be able to manage {slug}"


def test_limit_no_manageable_role_holds_a_sensitive_scope():
    """The property that actually keeps this safe, checked across EVERY role in
    the catalogue — so a newly added role can't quietly land in ICT's reach
    carrying users:write."""
    ict = _stub("it_support")
    breaches = {}
    for slug in SCHOOL_PERMISSION_PRESETS:
        if slug == "it_support":
            continue
        if _can_manage(ict, _stub(slug)):
            hits = [s for s in SENSITIVE_SCOPES if s in set(SCHOOL_PERMISSION_PRESETS[slug])]
            if hits:
                breaches[slug] = hits
    assert not breaches, f"ICT can manage accounts holding sensitive scopes: {breaches}"


def test_ict_does_not_hold_the_scopes_that_define_the_protected_tiers():
    """Stated from ICT's side too: the absences are deliberate, not incidental."""
    perms = set(SCHOOL_PERMISSION_PRESETS["it_support"])
    for scope in ("*", "users:delete", "settings:write", "audit_logs:read",
                  "hr:write", "school:write", "finance_admin:read",
                  "finance_admin:write", "payments:write", "imports:write"):
        assert scope not in perms, f"it_support must not hold {scope}"


# ── the guards, exercised for real against the DB ─────────────────────────────

async def _real(db, org, slug: str) -> User:
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug, status=UserStatus.ACTIVE, hashed_password="x", org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def test_ict_can_reset_a_teachers_password(db, org):
    ict = await _real(db, org, "it_support")
    teacher = await _real(db, org, "teacher")

    out = await reset_user_password(teacher.id, request=None, db=db, current_user=ict)
    assert out["temporary_password"] and out["force_password_change"] is True
    await db.refresh(teacher)
    assert teacher.hashed_password != "x"


@pytest.mark.parametrize("slug", ["student", "parent", "librarian"])
async def test_ict_can_reset_ordinary_accounts(db, org, slug):
    ict = await _real(db, org, "it_support")
    target = await _real(db, org, slug)
    out = await reset_user_password(target.id, request=None, db=db, current_user=ict)
    assert out["temporary_password"]


@pytest.mark.parametrize("slug", ["super_user", "org_admin", "accountant", "hr_manager"])
async def test_ict_cannot_reset_protected_accounts(db, org, slug):
    ict = await _real(db, org, "it_support")
    target = await _real(db, org, slug)

    with pytest.raises(HTTPException) as exc:
        await reset_user_password(target.id, request=None, db=db, current_user=ict)
    assert exc.value.status_code == 403
    await db.refresh(target)
    assert target.hashed_password == "x"       # credential untouched


# ── status changes carry the same bar ─────────────────────────────────────────

async def test_lower_tier_cannot_suspend_the_super_user(db, org):
    """Suspending an account is a denial of service against it — previously any
    users:write holder could switch off the Super User."""
    hr = await _real(db, org, "hr_manager")
    boss = await _real(db, org, "super_user")

    with pytest.raises(HTTPException) as exc:
        await update_user_status(boss.id, UserStatusUpdate(status=UserStatus.SUSPENDED),
                                 request=None, db=db, current_user=hr)
    assert exc.value.status_code == 403
    await db.refresh(boss)
    assert boss.status == UserStatus.ACTIVE


async def test_ict_cannot_suspend_an_admin(db, org):
    ict = await _real(db, org, "it_support")
    admin = await _real(db, org, "org_admin")

    with pytest.raises(HTTPException) as exc:
        await update_user_status(admin.id, UserStatusUpdate(status=UserStatus.SUSPENDED),
                                 request=None, db=db, current_user=ict)
    assert exc.value.status_code == 403


async def test_ict_can_still_suspend_an_ordinary_account(db, org):
    """The guard must not break the legitimate job — offboarding a leaver."""
    ict = await _real(db, org, "it_support")
    teacher = await _real(db, org, "teacher")

    out = await update_user_status(teacher.id, UserStatusUpdate(status=UserStatus.SUSPENDED),
                                   request=None, db=db, current_user=ict)
    assert out.status == UserStatus.SUSPENDED


async def test_super_user_can_still_suspend_anyone(db, org):
    boss = await _real(db, org, "super_user")
    admin = await _real(db, org, "org_admin")
    out = await update_user_status(admin.id, UserStatusUpdate(status=UserStatus.SUSPENDED),
                                   request=None, db=db, current_user=boss)
    assert out.status == UserStatus.SUSPENDED
