"""
Multi-Tenant Middleware & Utilities
====================================
Strategy: Subdomain-based tenant identification
  - dev.extracare.app  → org slug = "dev"
  - lagos-hospital.extracare.app → org slug = "lagos-hospital"

Fallback: X-Org-Slug header (for mobile apps / API clients)

Every authenticated request resolves to an org_id that is injected into
the request state. All DB queries then filter by this org_id automatically.
"""

import logging
from fastapi import Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.organization import Organization
from app.core.plans import plan_for, module_allowed_by_plan, modules_within_cap, plan_limit_detail
from app.core.workspace import effective_modules_for_org, is_module_enabled_for_org

_forbidden_logger = logging.getLogger("extracare.access")

# In-process denial counters. Keyed by (event, org_id, bucket) where bucket is
# the required_module or required_perm. Lets /admin/metrics surface tenants
# with abnormal 403 rates without pulling logs. Swap for Prometheus/statsd
# when we add a metrics backend.
_denial_counts: dict[tuple[str, str, str], int] = {}


def _bump_denial(event: str, org_id: str, bucket: str) -> None:
    key = (event, org_id or "_", bucket or "_")
    _denial_counts[key] = _denial_counts.get(key, 0) + 1


# Public alias — lets services outside core/ increment the same counters
# without reaching into a private name. All denial bookkeeping flows through
# this one function so /admin/metrics stays authoritative.
def bump_denial(event: str, org_id: str, bucket: str) -> None:
    _bump_denial(event, org_id, bucket)


def denial_counters_snapshot() -> list[dict]:
    return [
        {"event": e, "org_id": o, "bucket": b, "count": n}
        for (e, o, b), n in sorted(_denial_counts.items(), key=lambda kv: -kv[1])
    ]


def extract_slug_from_host(host: str) -> str | None:
    """Parse 'acme.extracare.app' → 'acme'. Returns None for bare domain."""
    # Strip port if present
    host = host.split(":")[0]
    parts = host.split(".")
    # extracare.app = 2 parts, sub.extracare.app = 3 parts
    if len(parts) >= 3:
        return parts[0]
    return None


async def resolve_tenant(request: Request, db: AsyncSession) -> Organization:
    """
    Resolves the current tenant from the request.
    Raises 404 if tenant not found or inactive.
    """
    slug = None

    # 1. Try subdomain
    host = request.headers.get("host", "")
    slug = extract_slug_from_host(host)

    # 2. Fallback to header (API clients, mobile)
    if not slug:
        slug = request.headers.get("X-Org-Slug")

    # 3. Fallback to query param (dev/testing only)
    if not slug and request.app.debug:
        slug = request.query_params.get("org")

    if not slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to determine organization. Provide X-Org-Slug header.",
        )

    result = await db.execute(
        select(Organization).where(
            Organization.slug == slug,
            Organization.is_active == True,
            Organization.is_deleted == False,
        )
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{slug}' not found.",
        )

    request.state.org = org
    request.state.org_id = org.id
    return org


def require_module(module_name: str):
    """
    Dependency factory: ensures the current org has a specific module enabled.
    Also resolves the tenant into request.state so downstream code can use it.
    Usage: Depends(require_module("school"))
    """
    from fastapi import Depends
    from app.database import get_db
    from app.deps import get_current_active_user

    async def _check(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_active_user),
    ):
        # Resolve org from authenticated user's org_id
        org: Organization = getattr(request.state, "org", None)
        if org is None:
            result = await db.execute(
                select(Organization).where(
                    Organization.id == current_user.org_id,
                    Organization.is_active == True,
                )
            )
            org = result.scalar_one_or_none()
            if not org:
                raise HTTPException(status_code=400, detail="Tenant not resolved.")
            request.state.org = org
            request.state.org_id = org.id

        if not is_module_enabled_for_org(org, module_name):
            _bump_denial("module_access_denied", org.id, module_name)
            _forbidden_logger.warning(
                "module_access_denied",
                extra={
                    "event": "module_access_denied",
                    "user_id": current_user.id,
                    "org_id": org.id,
                    "industry": org.industry.value if org.industry else None,
                    "required_module": module_name,
                    "path": request.url.path,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{module_name}' is not enabled for your organization.",
            )
    return _check


def require_role_module(module_name: str, action: str = "read"):
    """
    Combined guard: org must have `module_name` in modules_enabled AND
    the caller must hold the `<module_name>:<action>` permission (default
    action is `read`, which we auto-enforce on every module router).

    Kept orthogonal to `require_permission` — permission strings remain the
    primary RBAC mechanism. This dep just wires module + canonical-perm
    together so individual routers can't forget one.
    """
    from fastapi import Depends
    from app.database import get_db
    from app.deps import get_current_active_user

    required_perm = f"{module_name}:{action}"

    async def _check(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_active_user),
    ):
        org: Organization = getattr(request.state, "org", None)
        if org is None:
            result = await db.execute(
                select(Organization).where(
                    Organization.id == current_user.org_id,
                    Organization.is_active == True,
                )
            )
            org = result.scalar_one_or_none()
            if not org:
                raise HTTPException(status_code=400, detail="Tenant not resolved.")
            request.state.org = org
            request.state.org_id = org.id

        if not is_module_enabled_for_org(org, module_name):
            _bump_denial("module_access_denied", org.id, module_name)
            _forbidden_logger.warning(
                "module_access_denied",
                extra={
                    "event": "module_access_denied",
                    "user_id": current_user.id,
                    "org_id": org.id,
                    "industry": org.industry.value if org.industry else None,
                    "required_module": module_name,
                    "path": request.url.path,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{module_name}' is not enabled for your organization.",
            )

        # Onboarding gate — soft variant. Until setup completes we allow
        # the tenant's *active* (primary) module group through so they can
        # explore their chosen vertical while finishing setup, but block
        # unrelated modules. Super-admins bypass entirely.
        if org.onboarding_completed_at is None and not current_user.is_superadmin:
            from app.services.onboarding import module_is_in_primary_scope
            if not module_is_in_primary_scope(org, module_name):
                _bump_denial("onboarding_incomplete", org.id, module_name)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "onboarding_incomplete",
                        "onboarding_step": org.onboarding_step or "modules",
                    },
                )

        # Subscription-tier check. The module is enabled on the org, but the
        # plan may not actually permit it (e.g. admin downgraded from pro to
        # free without trimming modules_enabled). 402 tells the frontend to
        # route to /billing rather than showing a generic permission error.
        plan = plan_for(org.subscription_tier)
        effective_modules = effective_modules_for_org(org)
        if not module_allowed_by_plan(plan, module_name) or not modules_within_cap(plan, effective_modules):
            _bump_denial("plan_module_denied", org.id, module_name)
            _forbidden_logger.warning(
                "plan_module_denied",
                extra={
                    "event": "plan_module_denied",
                    "user_id": current_user.id,
                    "org_id": org.id,
                    "plan": plan.tier.value,
                    "required_module": module_name,
                    "path": request.url.path,
                },
            )
            # User-visible nudge before the exception tears down the tx.
            # Uses its own session so the caller's rollback doesn't wipe
            # the notification row. Awaited synchronously — the write is a
            # single INSERT and the caller is about to raise anyway.
            from app.services import notifications as _notif
            from app.models.notification import TYPE_PLAN_LIMIT
            await _notif.notify_fire_and_forget(
                org_id=org.id,
                user_id=current_user.id,
                type=TYPE_PLAN_LIMIT,
                title="Plan limit reached",
                message=f"Your current plan doesn't include the '{module_name}' module.",
                payload={
                    "reason": "module_not_allowed",
                    "module": module_name,
                    "current_plan": plan.tier.value,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=plan_limit_detail(
                    reason="module_not_allowed",
                    current_plan=plan.tier,
                ),
            )

        # Module-entry gate. A caller may open the module door if they hold the
        # broad `<module>:<action>` OR any fine-grained child scope (e.g. a
        # student with only `school:cbt:read` can enter the school module). The
        # specific feature is still enforced by the per-endpoint PermissionChecker.
        if not current_user.has_module_permission(module_name, action):
            _bump_denial("role_permission_denied", org.id, required_perm)
            _forbidden_logger.warning(
                "role_permission_denied",
                extra={
                    "event": "role_permission_denied",
                    "user_id": current_user.id,
                    "org_id": org.id,
                    "required_perm": required_perm,
                    "path": request.url.path,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: '{required_perm}'",
            )
    return _check
