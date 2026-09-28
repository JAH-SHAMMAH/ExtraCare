"""Fairview's portal has no plans, so nothing may refuse on tier grounds.

A teacher tried to start a live class and was told it "isn't enabled on your
plan". There is no plan to enable it on: the org sits on the FREE tier because
that is the enum's default, and FREE's catalog entry grants no features, so three
/live endpoints and /ai/assist all refused. Nobody had bought anything, and
nobody could.

These pin the two halves of the fix:
  * `has_feature` always allows, so `feature_disabled` is unreachable;
  * permissions are untouched, so the fix did not hand anyone new access.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.features import has_feature, require_feature, resolve_features
from app.core.plans import PLANS, plan_for
from app.models.organization import Organization, SubscriptionTier
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus


async def _user(db, org, preset: str) -> User:
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{preset}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=preset.title(), status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


# ── the helper itself ─────────────────────────────────────────────────────────

def test_every_flag_is_allowed_on_the_free_tier():
    """Fairview is FREE with `features = {}` — the exact row that refused."""
    org = Organization(id=str(uuid.uuid4()), name="Fairview School", slug="fairview",
                       subscription_tier=SubscriptionTier.FREE, features={})
    for flag in ("livestream", "ai_assistant", "advanced_reports", "sso"):
        assert has_feature(org, flag) is True, f"{flag} refused on the tier we run"


def test_it_allows_flags_no_plan_has_ever_defined():
    """An unknown flag used to be implicitly False, so a new capability shipped
    switched OFF for everyone until someone edited the plan catalog."""
    org = Organization(id=str(uuid.uuid4()), name="X", slug="x",
                       subscription_tier=SubscriptionTier.FREE, features={})
    assert has_feature(org, "something_invented_next_year") is True


def test_it_allows_even_when_the_org_row_is_missing():
    """A request whose org could not be resolved must not become a plan refusal."""
    assert has_feature(None, "livestream") is True


def test_an_explicit_per_tenant_false_no_longer_refuses():
    """`features: {"livestream": False}` was the clawback path. With no plans to
    claw back to, it must not be a way to reintroduce a tier refusal by hand."""
    org = Organization(id=str(uuid.uuid4()), name="X", slug="x",
                       subscription_tier=SubscriptionTier.FREE,
                       features={"livestream": False})
    assert has_feature(org, "livestream") is True


def test_the_tier_column_is_still_readable_for_display():
    """Left in place, merely unread. The billing page still has something to show,
    and restoring gating stays a one-line change rather than a migration."""
    org = Organization(id=str(uuid.uuid4()), name="X", slug="x",
                       subscription_tier=SubscriptionTier.FREE, features={})
    assert org.subscription_tier is SubscriptionTier.FREE
    assert plan_for(org.subscription_tier).name == "Free"
    # resolve_features still computes the catalog's real answer...
    assert resolve_features(org).get("livestream", False) is False
    # ...and has_feature deliberately disagrees with it, because that map
    # describes a price list, not what this product permits.
    assert has_feature(org, "livestream") is True


# ── the route dependency ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_feature_lets_a_teacher_through(db, org):
    """The dependency is kept so routes still say which capability they are, but
    it must no longer refuse. Driven as a real teacher, not an admin."""
    teacher = await _user(db, org, "teacher")
    check = require_feature("livestream")

    class _Req:
        class state:
            org = None

    # No exception is the assertion.
    await check(request=_Req(), db=db, current_user=teacher)


@pytest.mark.asyncio
async def test_a_teacher_can_start_a_live_session(db, org):
    """The reported failure, end to end: a teacher starting a live class."""
    from app.routers.live import start_session
    from app.schemas.live import LiveSessionCreate

    teacher = await _user(db, org, "teacher")
    res = await start_session(
        data=LiveSessionCreate(title="Biology - JSS1 A"),
        db=db, current_user=teacher)
    assert res.title == "Biology - JSS1 A"
    assert res.is_active is True


@pytest.mark.asyncio
async def test_no_gated_route_can_answer_feature_disabled(db, org):
    """Whatever the four gated endpoints refuse for in future, it must not be a
    plan. Asserted against the dependency every one of them declares."""
    teacher = await _user(db, org, "teacher")

    class _Req:
        class state:
            org = None

    for flag in ("livestream", "ai_assistant"):
        try:
            await require_feature(flag)(request=_Req(), db=db, current_user=teacher)
        except HTTPException as e:  # pragma: no cover - the failure path
            detail = e.detail if isinstance(e.detail, dict) else {}
            pytest.fail(f"{flag} refused with {detail.get('error')}")


# ── permissions are untouched ─────────────────────────────────────────────────

def test_removing_the_plan_gate_granted_nobody_new_permissions():
    """The fix must not be a back door. `livestream` was never a permission, and
    no preset gained one — a student still cannot manage a classroom."""
    student = set(SCHOOL_PERMISSION_PRESETS["student"])
    teacher = set(SCHOOL_PERMISSION_PRESETS["teacher"])
    assert "school:classroom:manage" in teacher
    assert "school:classroom:manage" not in student
    for preset in SCHOOL_PERMISSION_PRESETS.values():
        assert "livestream" not in preset
        assert "ai_assistant" not in preset


def test_the_plan_catalog_still_exists_for_billing():
    """Not deleted — the billing page reads it, and a future pricing change
    should not have to reconstruct it."""
    assert SubscriptionTier.FREE in PLANS
    assert PLANS[SubscriptionTier.PRO].monthly_price_ngn > 0


# ── the honest replacement for the gate ───────────────────────────────────────

@pytest.mark.asyncio
async def test_ice_config_says_when_no_turn_relay_is_configured(db, org):
    """Removing the gate turns a clear (wrong) refusal into a silent connection
    failure for anyone behind symmetric NAT. The notice must name the settings,
    or the next person has a call that never connects and nothing to read."""
    from app.routers.live import ice_config

    teacher = await _user(db, org, "teacher")
    res = await ice_config(current_user=teacher)

    assert res["iceServers"], "STUN should still be offered"
    assert res["turn_configured"] is False
    assert "TURN_URLS" in res["turn_notice"]
    assert "TURN_SECRET" in res["turn_notice"]
    assert "will not connect" in res["turn_notice"]
