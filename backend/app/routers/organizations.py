"""
Platform-level organization management.

Routes here are super-admin only and affect tenant-wide state
(e.g. industry, which fundamentally reshapes which product shell
a tenant sees). Tenant admins cannot call these endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.permissions import require_superadmin
from app.core.ratelimit import rate_limit
from app.deps import get_current_active_user
from app.models.audit import AuditAction
from app.models.organization import Organization, IndustryType
from app.models.user import User, UserStatus
from app.schemas.auth import IndustryLiteral
from app.services.audit_service import log_action
from app.services import onboarding as onboarding_svc
from app.core.workspace import get_default_modules_for_industry, validate_module_for_workspace, workspace_for
from app.models.role import Role, permission_presets_for_industry


router = APIRouter(prefix="/organizations", tags=["Organizations (Platform)"])


class IndustryChangeRequest(BaseModel):
    industry: IndustryLiteral
    modules_enabled: list[str] | None = None  # optional explicit override


class OnboardingAdvanceRequest(BaseModel):
    """Target step must be the one immediately after the current persisted
    step — no skipping. The service also re-evaluates DB state, so a caller
    cannot advance past a step whose condition hasn't been met."""
    step: str


class FeatureToggleRequest(BaseModel):
    """Sparse patch — only keys present in `features` are updated. To clear
    an override (fall back to plan default), send the key with value null.
    We don't want an empty PATCH body to nuke the whole flag map."""
    features: dict[str, bool | None]


@router.get("", summary="List all organizations (super-admin only)")
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    rows = (await db.execute(
        select(Organization).where(Organization.is_deleted == False).order_by(Organization.created_at.desc())
    )).scalars().all()

    # Per-org active-user counts in one round-trip.
    counts = dict((await db.execute(
        select(User.org_id, func.count(User.id))
        .where(User.is_deleted == False, User.status == UserStatus.ACTIVE)
        .group_by(User.org_id)
    )).all())

    return [
        {
            "id": o.id,
            "name": o.name,
            "slug": o.slug,
            "industry": o.industry.value if o.industry else None,
            "modules_enabled": list(o.modules_enabled or []),
            "subscription_tier": o.subscription_tier.value if o.subscription_tier else None,
            "active_users": counts.get(o.id, 0),
            "is_active": o.is_active,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in rows
    ]


@router.get("/{org_id}", summary="Inspect a single organization (super-admin only)")
async def get_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    users = (await db.execute(
        select(User).options(selectinload(User.roles))
        .where(User.org_id == org_id, User.is_deleted == False)
        .order_by(User.created_at.asc())
    )).scalars().all()

    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "industry": org.industry.value if org.industry else None,
        "modules_enabled": list(org.modules_enabled or []),
        "subscription_tier": org.subscription_tier.value if org.subscription_tier else None,
        "max_users": org.max_users,
        "is_active": org.is_active,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "status": u.status.value if u.status else None,
                "is_superadmin": u.is_superadmin,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "roles": [{"slug": r.slug, "name": r.name} for r in (u.roles or [])],
            }
            for u in users
        ],
    }


@router.patch(
    "/{org_id}/industry",
    summary="Change an organization's industry (super-admin only)",
    dependencies=[Depends(rate_limit("org_industry", max_hits=10, window_seconds=60))],
)
async def change_industry(
    org_id: str,
    payload: IndustryChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_superadmin),
):
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    old_industry = org.industry.value if org.industry else None
    old_modules = list(org.modules_enabled or [])

    new_industry_enum = IndustryType(payload.industry)
    if new_industry_enum == org.industry and payload.modules_enabled is None:
        return {"detail": "No change.", "industry": old_industry}

    org.industry = new_industry_enum
    # If caller didn't provide an explicit module set, leave the existing
    # modules_enabled alone — industry is a template, not a truncation.
    # This is deliberate: we don't want to nuke opt-in modules when the
    # label changes (e.g. a school org that also opted into `inventory`).
    if payload.modules_enabled is not None:
        workspace = workspace_for(payload.industry)
        invalid = [
            module for module in payload.modules_enabled
            if not validate_module_for_workspace(workspace, module)[0]
        ]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Modules not available for {workspace.label} workspace: {', '.join(invalid)}",
            )
        org.modules_enabled = payload.modules_enabled
    else:
        # Industry changes intentionally reshape the active product shell.
        # Existing data stays intact; entry points move to the new workspace.
        org.modules_enabled = get_default_modules_for_industry(payload.industry)

    await _sync_system_roles_for_org(db, org)

    await log_action(
        db, AuditAction.ORG_INDUSTRY_CHANGED, org.id,
        actor=actor,
        resource_type="Organization",
        resource_id=org.id,
        resource_label=org.name,
        request=request,
        old_values={"industry": old_industry, "modules_enabled": old_modules},
        new_values={
            "industry": org.industry.value,
            "modules_enabled": list(org.modules_enabled or []),
        },
        severity="warning",
    )

    await db.commit()
    await db.refresh(org)

    return {
        "id": org.id,
        "slug": org.slug,
        "industry": org.industry.value,
        "modules_enabled": list(org.modules_enabled or []),
    }


async def _sync_system_roles_for_org(db: AsyncSession, org: Organization) -> None:
    industry = org.industry.value if org.industry else None
    presets = permission_presets_for_industry(industry)
    existing = (await db.execute(
        select(Role).where(Role.org_id == org.id, Role.is_system == True)
    )).scalars().all()
    by_slug = {role.slug: role for role in existing}

    for slug, perms in presets.items():
        if slug == "super_admin":
            continue
        role = by_slug.get(slug)
        if role is None:
            db.add(Role(
                name=slug.replace("_", " ").title(),
                slug=slug,
                permissions=list(perms),
                org_id=org.id,
                is_system=True,
            ))
        else:
            role.permissions = list(perms)


@router.patch(
    "/{org_id}/features",
    summary="Toggle per-tenant feature flags (super-admin only)",
)
async def toggle_features(
    org_id: str,
    payload: FeatureToggleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_superadmin),
):
    from app.core.features import resolve_features

    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    before = dict(org.features or {})
    merged = dict(before)
    for key, value in payload.features.items():
        if value is None:
            # Null clears the override — effective flag falls back to the
            # plan default. This is the only way to remove a stuck key.
            merged.pop(key, None)
        else:
            merged[key] = bool(value)
    org.features = merged

    await log_action(
        db, AuditAction.ORG_FEATURES_CHANGED, org.id,
        actor=actor,
        resource_type="Organization",
        resource_id=org.id,
        resource_label=org.name,
        request=request,
        old_values={"features": before},
        new_values={"features": merged},
        severity="info",
    )

    await db.commit()
    await db.refresh(org)

    return {
        "id": org.id,
        "slug": org.slug,
        "features_overrides": dict(org.features or {}),
        "features_effective": resolve_features(org),
    }


@router.get(
    "/{org_id}/onboarding",
    summary="Inspect onboarding state + why the current step is blocked",
)
async def get_onboarding(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_active_user),
):
    """Surfaces the current step plus a concrete requirement string for
    the frontend's setup wizard / support debugging. Same-tenant admins
    see their own state; super-admins see any tenant."""
    if actor.org_id != org_id and not actor.is_superadmin:
        raise HTTPException(status_code=403, detail="Cross-tenant onboarding is not permitted.")

    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    return await onboarding_svc.diagnose(db, org)


@router.patch(
    "/{org_id}/onboarding",
    summary="Advance tenant onboarding to the next step",
)
async def advance_onboarding(
    org_id: str,
    payload: OnboardingAdvanceRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_active_user),
):
    """Tenant admins drive this during guided setup. Same-tenant only unless
    super-admin. The service enforces strict step progression against real
    DB state, so a crafted payload cannot skip ahead."""
    if actor.org_id != org_id and not actor.is_superadmin:
        raise HTTPException(status_code=403, detail="Cross-tenant onboarding is not permitted.")

    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    old_step = org.onboarding_step or "modules"
    try:
        new_step = await onboarding_svc.advance(db, org, payload.step)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if new_step != old_step:
        await log_action(
            db, AuditAction.ORG_ONBOARDING_ADVANCED, org.id,
            actor=actor,
            resource_type="Organization",
            resource_id=org.id,
            resource_label=org.name,
            request=request,
            old_values={"onboarding_step": old_step},
            new_values={"onboarding_step": new_step},
            severity="info",
        )
        await db.commit()
        await db.refresh(org)

    return {
        "id": org.id,
        "onboarding_step": org.onboarding_step,
        "onboarding_completed": org.onboarding_completed_at is not None,
    }
