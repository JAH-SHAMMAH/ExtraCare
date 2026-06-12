"""
Plan catalog — single source of truth for what each subscription tier allows.

The catalog here is read at request time by the module/user guards. Changing
a plan's caps here immediately tightens or relaxes enforcement for every
tenant on that plan. No migrations required.

Structure is intentionally flat so that (a) a future billing adapter can
consume it to build checkout payloads, and (b) tests can monkeypatch a
single dict without threading config through fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.models.organization import SubscriptionTier


# Sentinel for "no cap" — tests assert against this so None stays available
# for "not specified" on feature flags.
UNLIMITED = -1

# Module keys that exist at all today. Kept here so plans can reference them
# without importing the router modules (keeps this file side-effect-free).
ALL_MODULES = frozenset({
    "school", "attendance", "grades", "timetable",
    "hospital", "appointments", "emr", "billing",
    "business", "payroll", "inventory", "finance",
})


@dataclass(frozen=True)
class Plan:
    tier: SubscriptionTier
    name: str
    # How many distinct module keys the tenant may have in modules_enabled.
    # UNLIMITED disables the check. Note: "module keys" counts every key,
    # so {"school","attendance","grades"} counts as 3. See allowed_modules
    # for which specific keys are permitted regardless of count.
    max_modules: int
    # Hard cap on active (non-deleted) users in the org. UNLIMITED disables.
    max_users: int
    # None means "any module in ALL_MODULES". A frozenset narrows the plan
    # to specific keys — used to model free-tier gating away from hybrid.
    allowed_modules: frozenset[str] | None = None
    # Flags this plan turns on by default. Per-tenant overrides stack on top.
    default_features: tuple[str, ...] = ()
    # Monthly price in NGN. Paystack works in kobo (NGN * 100) — the
    # billing router does the conversion. 0 means "not on sale" (free
    # tier or legacy plans that are no longer offered).
    monthly_price_ngn: int = 0
    # Lifetime recording storage cap (MB) for the Livestream module.
    # UNLIMITED disables the check. A plan without `livestream` enabled
    # never reaches the quota check, so this field only matters for
    # tiers that actually include the feature.
    recording_storage_mb: int = 0


PLANS: dict[SubscriptionTier, Plan] = {
    SubscriptionTier.FREE: Plan(
        tier=SubscriptionTier.FREE,
        name="Free",
        max_modules=1,
        max_users=10,
    ),
    SubscriptionTier.PRO: Plan(
        tier=SubscriptionTier.PRO,
        name="Pro",
        max_modules=2,
        max_users=50,
        default_features=("advanced_reports", "livestream"),
        monthly_price_ngn=5_000,
        recording_storage_mb=10_000,  # 10 GB
    ),
    SubscriptionTier.ENTERPRISE: Plan(
        tier=SubscriptionTier.ENTERPRISE,
        name="Enterprise",
        max_modules=UNLIMITED,
        max_users=UNLIMITED,
        default_features=("advanced_reports", "ai_assistant", "sso", "livestream"),
        monthly_price_ngn=25_000,
        recording_storage_mb=UNLIMITED,
    ),
    # Legacy tiers map to pro/enterprise so pre-existing rows keep working
    # without us having to backfill. New signups never land here.
    SubscriptionTier.STARTER: Plan(
        tier=SubscriptionTier.STARTER, name="Starter (legacy)",
        max_modules=2, max_users=50,
    ),
    SubscriptionTier.GROWTH: Plan(
        tier=SubscriptionTier.GROWTH, name="Growth (legacy)",
        max_modules=UNLIMITED, max_users=500,
    ),
}


def plan_for(tier: SubscriptionTier | str | None) -> Plan:
    """Resolve a tier value to its Plan. Unknown/None → free, defensive."""
    if tier is None:
        return PLANS[SubscriptionTier.FREE]
    if isinstance(tier, str):
        try:
            tier = SubscriptionTier(tier)
        except ValueError:
            return PLANS[SubscriptionTier.FREE]
    return PLANS.get(tier, PLANS[SubscriptionTier.FREE])


def module_allowed_by_plan(plan: Plan, module: str) -> bool:
    """Is `module` permitted on this plan, ignoring current usage?"""
    if plan.allowed_modules is not None and module not in plan.allowed_modules:
        return False
    return True


def modules_within_cap(plan: Plan, modules_enabled: Iterable[str]) -> bool:
    """Does the org's current module count fit under the plan's cap?"""
    if plan.max_modules == UNLIMITED:
        return True
    return len(list(modules_enabled)) <= plan.max_modules


def users_within_cap(plan: Plan, current_count: int) -> bool:
    if plan.max_users == UNLIMITED:
        return True
    return current_count < plan.max_users


# Canonical upgrade path. Keep as a table (not if/elif) so a future
# pricing shake-up — e.g. adding a "team" tier between free and pro —
# is a one-line edit that every 402 response picks up automatically.
_UPGRADE_PATH: dict[SubscriptionTier, SubscriptionTier] = {
    SubscriptionTier.FREE: SubscriptionTier.PRO,
    SubscriptionTier.STARTER: SubscriptionTier.PRO,
    SubscriptionTier.PRO: SubscriptionTier.ENTERPRISE,
    SubscriptionTier.GROWTH: SubscriptionTier.ENTERPRISE,
    SubscriptionTier.ENTERPRISE: SubscriptionTier.ENTERPRISE,
}


def suggested_upgrade_tier(current: SubscriptionTier) -> SubscriptionTier:
    return _UPGRADE_PATH.get(current, SubscriptionTier.PRO)


def plan_limit_detail(
    *,
    reason: str,
    current_plan: SubscriptionTier | str,
    upgrade_url: str = "/billing",
) -> dict:
    """Canonical body for every 402 the plan guard raises. The frontend
    keys off `reason` to decide whether to open the user-cap modal or
    the module-upsell sheet, then uses `upgrade_url` for checkout."""
    current = current_plan if isinstance(current_plan, SubscriptionTier) else SubscriptionTier(current_plan)
    return {
        "error": "plan_limit_exceeded",
        "reason": reason,
        "current_plan": current.value,
        "required_plan": suggested_upgrade_tier(current).value,
        "upgrade_url": upgrade_url,
    }
