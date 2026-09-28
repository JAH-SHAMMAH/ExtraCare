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
    """Always True. Fairview's portal has no plans, so nothing is sold per tier.

    This is ONE helper rather than edits at four call sites, so `require_feature`
    keeps its shape and the routes keep their dependency lists: if tiers ever come
    back, this function is the only thing to restore.

    WHAT THIS DOES NOT CHANGE: permissions. `livestream` was never a permission —
    who may start a live class is still decided by the scope on the route and the
    ownership checks inside it. A teacher gains nothing here they could not already
    have been granted; they simply stop being told their plan forbids it.

    `subscription_tier` is deliberately LEFT IN PLACE and merely unread. Dropping
    the column would be a migration in service of a decision that might reverse,
    and `resolve_features` below still computes the real map for the billing page
    to display. Nothing gates on it.

    This is why the four gated endpoints (three on /live, one on /ai/assist) stop
    returning `feature_disabled`: on a FREE tier, which Fairview is, the plan
    catalog grants no features at all, so every one of them refused.
    """
    return True


def resolved_feature(org: Organization | None, flag: str) -> bool:
    """What the plan catalog WOULD say — for display, never for gating.

    Kept separate from `has_feature` so a reader cannot mistake one for the other:
    the billing page may want to show what a tier includes, and that is a different
    question from whether the product allows something.
    """
    return bool(resolve_features(org).get(flag, False))


def require_feature(flag: str):
    """Route dependency. Retained deliberately, and currently a no-op.

    It stays for two reasons: the four routes that declare it keep documenting
    WHICH capability they are, and if per-tenant gating ever returns it comes back
    in one place rather than being re-threaded through the routes.

    It no longer refuses anything, because `has_feature` always allows. The 403 +
    `feature_disabled` body below is therefore unreachable; it is left standing so
    that restoring gating is a one-line change to `has_feature` rather than
    rebuilding the error contract the frontend already understands.
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
