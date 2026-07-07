from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType, SubscriptionTier
from app.models.role import Role, permission_presets_for_industry
from app.core.workspace import effective_modules_for_org, get_default_modules_for_industry
from app.core.single_school import get_school_org
from app.core.security import (
    verify_password, hash_password, create_access_token,
    create_refresh_token, decode_token, generate_secure_token,
    validate_password_strength,
)
from app.core.cookies import set_auth_cookies, clear_auth_cookies, issue_csrf_token
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest,
    RegisterOrgRequest, PasswordResetRequest, PasswordResetConfirm, UserMeResponse,
    ChangePasswordRequest,
)
from app.services.audit_service import log_action
from app.models.audit import AuditAction
from app.core.ratelimit import rate_limit_ip
from app.deps import get_current_user
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post(
    "/register",
    status_code=201,
    summary="Register a new organization + admin user",
    dependencies=[Depends(rate_limit_ip("register"))],
)
async def register_organization(
    data: RegisterOrgRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    """
    One-shot registration: creates the organization, default roles, and the first admin user.
    This is the onboarding entry point.
    """
    # Single-school mode is a dedicated portal for one school — there is no
    # self-service organisation creation. Accounts are provisioned by an
    # administrator (or the seed), never by public signup. Endpoint is left in
    # place so multi-tenant deployments keep working.
    if settings.SINGLE_SCHOOL_MODE:
        raise HTTPException(
            status_code=403,
            detail="Public registration is disabled. Contact your school administrator for access.",
        )

    # Check slug uniqueness
    existing_org = await db.execute(select(Organization).where(Organization.slug == data.org_slug))
    if existing_org.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Organization slug already taken.")

    # Create organization
    org = Organization(
        name=data.org_name,
        slug=data.org_slug,
        industry=IndustryType(data.industry),
        subscription_tier=SubscriptionTier.FREE,
        modules_enabled=get_default_modules_for_industry(data.industry),
        max_users=settings.FREE_TIER_USER_LIMIT,
    )
    db.add(org)
    await db.flush()

    # Seed default roles for this org
    default_roles = _create_default_roles(org.id, data.industry)
    for role in default_roles:
        db.add(role)
    await db.flush()

    admin_role = next(r for r in default_roles if r.slug == "org_admin")

    # Create admin user
    admin = User(
        email=data.admin_email,
        full_name=data.admin_name,
        hashed_password=hash_password(data.password),
        org_id=org.id,
        status=UserStatus.ACTIVE,
        email_verified=True,
        roles=[admin_role],
    )
    db.add(admin)
    await db.flush()

    await log_action(db, AuditAction.USER_CREATED, org.id, actor=admin,
                     resource_type="Organization", resource_id=org.id, resource_label=org.name, request=request)

    # Lifecycle marker — powers signup→activation funnel on the growth
    # dashboard. Fire-and-forget; a failed usage write mustn't block signup.
    try:
        from app.services.usage import track as _track_usage
        _track_usage(org.id, "platform", "onboarding_started")
    except Exception:
        pass

    access_token = create_access_token(_identity_claims(admin, org))
    refresh_token = create_refresh_token({"sub": admin.id, "org": org.id})

    if settings.COOKIE_AUTH_ENABLED:
        set_auth_cookies(response, access_token, refresh_token, issue_csrf_token())

    return {
        "message": "Organization created successfully.",
        "org_slug": org.slug,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_ip("login"))],
)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    # Normalize the submitted email once. Stored emails are lower-cased, and
    # the domain gate / user lookup both rely on a canonical form.
    email = (data.email or "").strip().lower()

    # ── Tenant resolution ────────────────────────────────────────────────
    # Single-school mode ignores any submitted org_slug and resolves the one
    # canonical organisation server-side — there is no tenant to choose. The
    # legacy slug path is preserved for non-single-school deployments.
    if settings.SINGLE_SCHOOL_MODE:
        org = await get_school_org(db)
        if not org or not org.is_active:
            raise HTTPException(
                status_code=503,
                detail="School portal is not configured yet. Please contact your administrator.",
            )
    else:
        org_result = await db.execute(
            select(Organization).where(Organization.slug == data.org_slug, Organization.is_active == True)
        )
        org = org_result.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found.")

    # ── Email-domain restriction ─────────────────────────────────────────
    # Necessary-but-not-sufficient: only @<domain> addresses may authenticate,
    # but the account must still exist and pass every credential check below.
    # Checked before any user lookup so we never auto-provision and never leak
    # which accounts exist. Audited as a failed login.
    if not settings.email_allowed(email):
        await log_action(db, AuditAction.LOGIN_FAILED, org.id, request=request,
                         metadata={"email": email, "reason": "domain_not_allowed"})
        raise HTTPException(
            status_code=403,
            detail=f"Access is restricted to @{settings.allowed_email_domain} accounts.",
        )

    # Find user within org (eager-load roles for permissions check)
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(
            User.email == email,
            User.org_id == org.id,
            User.is_deleted == False,
        )
    )
    user = user_result.scalar_one_or_none()

    if not user or not user.hashed_password:
        await log_action(db, AuditAction.LOGIN_FAILED, org.id, request=request,
                         metadata={"email": email})
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(status_code=403, detail="Account suspended.")

    if not verify_password(data.password, user.hashed_password):
        failed = int(user.failed_login_attempts or 0) + 1
        user.failed_login_attempts = str(failed)
        if failed >= 5:
            user.status = UserStatus.LOCKED
        await log_action(db, AuditAction.LOGIN_FAILED, org.id, actor=user, request=request)
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    # Successful login
    user.failed_login_attempts = "0"
    user.last_login_at = datetime.now(timezone.utc)
    forwarded = request.headers.get("X-Forwarded-For")
    user.last_login_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)

    await log_action(db, AuditAction.LOGIN, org.id, actor=user, request=request)

    claims = _identity_claims(user, org)
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token({"sub": user.id, "org": org.id})

    if settings.COOKIE_AUTH_ENABLED:
        set_auth_cookies(response, access_token, refresh_token, issue_csrf_token())

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserMeResponse.from_user(user, org),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_ip("refresh"))],
)
async def refresh_token(
    data: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    from jose import JWTError
    # Body carries the refresh token for Bearer/API clients; cookie-auth clients
    # carry it in the httpOnly refresh cookie.
    raw = data.refresh_token if (data and data.refresh_token) else None
    if not raw and settings.COOKIE_AUTH_ENABLED:
        raw = request.cookies.get("refresh_token")
    if not raw:
        raise HTTPException(status_code=401, detail="Missing refresh token.")
    try:
        payload = decode_token(raw)
        if payload.get("type") != "refresh":
            raise ValueError()
        user_id = payload["sub"]
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    org = (await db.execute(select(Organization).where(Organization.id == user.org_id))).scalar_one_or_none()

    access_token = create_access_token(_identity_claims(user, org))
    new_refresh = create_refresh_token({"sub": user.id, "org": user.org_id})

    if settings.COOKIE_AUTH_ENABLED:
        set_auth_cookies(response, access_token, new_refresh, issue_csrf_token())

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserMeResponse.from_user(user, org),
    )


@router.post("/logout", summary="Clear auth cookies (cookie-auth clients)")
async def logout(response: Response):
    """Clears the httpOnly auth cookies. Safe to call without a valid access
    token (the cookie may already be expired). Bearer/API clients simply drop
    their token client-side — this is a harmless no-op for them."""
    clear_auth_cookies(response)
    return {"detail": "Logged out."}


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = (await db.execute(select(Organization).where(Organization.id == current_user.org_id))).scalar_one_or_none()
    if org is not None:
        # Auto-advance onboarding from DB state — lets imports, direct SQL,
        # or sibling admin actions progress the flow without a PATCH.
        from app.services.onboarding import evaluate as evaluate_onboarding
        await evaluate_onboarding(db, org)
    return UserMeResponse.from_user(current_user, org)


@router.post("/change-password", summary="Change your own password")
async def change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Self-service password change. Verifies the current password, enforces
    strength on the new one, and clears force_password_change — this is what a user
    does to satisfy an admin-initiated reset."""
    user = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
    if not user or not user.hashed_password or not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    violations = validate_password_strength(data.new_password)
    if violations:
        raise HTTPException(status_code=422, detail=" ".join(violations))
    if verify_password(data.new_password, user.hashed_password):
        raise HTTPException(status_code=422, detail="New password must differ from the current one.")
    user.hashed_password = hash_password(data.new_password)
    user.force_password_change = False
    await db.flush()
    await log_action(
        db, AuditAction.PASSWORD_RESET, user.org_id, actor=user,
        resource_type="User", resource_id=user.id, resource_label=user.full_name,
        request=request,
    )
    return {"changed": True}


def _identity_claims(user, org: Organization) -> dict:
    """Access-token claims. `industry` + `modules` are denormalized here
    so downstream services can short-circuit without a DB round-trip.
    Tokens are short-lived — a refresh reseats any drift."""
    return {
        "sub": user.id,
        "org": org.id,
        "industry": org.industry.value if org.industry else None,
        "modules": effective_modules_for_org(org),
    }


def _default_modules_for(industry: str) -> list[str]:
    """Seeded modules at signup. Each entry is a primary module key the
    sidebar and route guards actually consult; sub-feature keys
    (attendance, grades, billing, etc.) are NOT enumerated here because
    nothing in the codebase gates on them — they'd only inflate the
    plan's module count. Hybrid orgs must land on Enterprise to actually
    use all three; on Free/Pro the plan guard will 402 them to upgrade."""
    mapping = {
        "school": ["school"],
        "hospital": ["hospital"],
        "business": ["business"],
        "hybrid": ["school", "hospital", "business"],
    }
    return mapping.get(industry, [])


def _create_default_roles(org_id: str, industry: str) -> list[Role]:
    roles = []
    for slug, perms in permission_presets_for_industry(industry).items():
        if slug == "super_admin":
            continue  # platform-only
        roles.append(Role(
            name=slug.replace("_", " ").title(),
            slug=slug,
            permissions=perms,
            org_id=org_id,
            is_system=True,
        ))
    return roles
