"""
Feature flags — per-tenant booleans, resolved from plan defaults + org overrides.

Layering (highest wins, always):
  1. org.features[key]        ← explicit per-tenant override (bool)
  2. plan.default_features    ← keys enabled by the tenant's current plan
  3. implicit False           ← unknown flags are always off

Kept intentionally tiny: no rollout percentages, no targeting rules, no
provider integration. When we need any of that we'll wire LaunchDarkly or
similar behind the same `has_feature` / `require_feature` call sites without
changing route code.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import plan_for
from app.models.organization import Organization


def resolve_features(org: Organization | None) -> dict[str, bool]:
    """Effective flag map for `org`. Plan defaults seed the dict; the org's
    `features` JSON overrides key-by-key so a per-tenant False can disable
    something the plan enabled (useful for clawbacks) and vice versa."""
    if org is None:
        return {}
    plan = plan_for(org.subscription_tier)
    merged: dict[str, bool] = {k: True for k in plan.default_features}
    overrides = org.features or {}
    # Strict-True comparison: truthy strings, numbers, or stray dicts that
    # land in the JSON column don't accidentally enable a flag. Only a
    # literal True (from the validated PATCH path) counts as on.
    for k, v in overrides.items():
        merged[k] = (v is True)
    return merged


def has_feature(org: Organization | None, flag: str) -> bool:
    return bool(resolve_features(org).get(flag, False))


def require_feature(flag: str):
    """Route dependency — 403 if the tenant doesn't have `flag` enabled.

    We use 403 (not 402) because feature flags are frequently used for beta
    gating where "upgrade to fix it" doesn't apply — an enterprise tenant
    can still have `ai_assistant=false`. The frontend distinguishes between
    402 (open /billing) and 403+feature_disabled (hide the entry point).
    """
    from app.database import get_db
    from app.deps import get_current_active_user

    async def _check(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_active_user),
    ):
        org: Organization | None = getattr(request.state, "org", None)
        if org is None:
            org = (await db.execute(
                select(Organization).where(Organization.id == current_user.org_id)
            )).scalar_one_or_none()
            if org is not None:
                request.state.org = org
                request.state.org_id = org.id

        if not has_feature(org, flag):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_disabled",
                    "flag": flag,
                },
            )

    return _check
