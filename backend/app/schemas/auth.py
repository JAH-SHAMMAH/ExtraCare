from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.core.security import validate_password_strength


IndustryLiteral = Literal["school", "hospital", "business", "hybrid"]


class PlanSummary(BaseModel):
    """What the frontend needs to decide 'can the user do this, or should
    we route them to /billing?'. Caps are copied from the plan catalog at
    response time so downgrades take effect immediately on the next /me."""
    tier: str
    name: str
    max_modules: int  # -1 = unlimited
    max_users: int    # -1 = unlimited


class OrganizationSummary(BaseModel):
    """Org identity shipped alongside auth responses so the client can
    render an industry-specific shell without a second round-trip."""
    id: str
    name: str
    slug: str
    industry: IndustryLiteral
    subscription_tier: str
    modules_enabled: list[str]
    modules_configured: list[str] = []
    workspace: dict[str, object] = {}
    logo_url: str | None = None
    primary_color: str | None = None
    plan: PlanSummary | None = None
    features: dict[str, bool] = {}
    onboarding_step: str = "modules"
    onboarding_completed: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def from_org(cls, org) -> "OrganizationSummary":
        from app.core.plans import plan_for
        from app.core.features import resolve_features
        from app.core.workspace import effective_modules_for_org, workspace_for
        plan = plan_for(org.subscription_tier)
        workspace = workspace_for(org.industry.value if org.industry else None)
        return cls(
            id=org.id,
            name=org.name,
            slug=org.slug,
            industry=org.industry.value,
            subscription_tier=org.subscription_tier.value,
            modules_enabled=effective_modules_for_org(org),
            modules_configured=list(org.modules_enabled or []),
            logo_url=org.logo_url,
            primary_color=org.primary_color,
            plan=PlanSummary(
                tier=plan.tier.value,
                name=plan.name,
                max_modules=plan.max_modules,
                max_users=plan.max_users,
            ),
            features=resolve_features(org),
            onboarding_step=org.onboarding_step or "modules",
            onboarding_completed=org.onboarding_completed_at is not None,
            workspace={
                "type": workspace.type.value,
                "label": workspace.label,
                "dashboard_type": workspace.dashboard_type,
                "modules": sorted(workspace.all_modules),
                "features": sorted(workspace.features),
            },
        )


class UserMeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: str | None
    status: str
    org_id: str
    primary_role: str
    permissions: list[str]
    mfa_enabled: bool
    force_password_change: bool = False
    org: OrganizationSummary | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user, org=None) -> "UserMeResponse":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            status=user.status.value,
            org_id=user.org_id,
            primary_role=user.primary_role,
            permissions=list(user.permissions),
            mfa_enabled=user.mfa_enabled,
            force_password_change=bool(getattr(user, "force_password_change", False)),
            org=OrganizationSummary.from_org(org) if org is not None else None,
        )


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    # Optional: ignored in single-school mode (the server resolves the one
    # organisation). Still honoured by multi-tenant deployments for slug-based
    # tenant routing.
    org_slug: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserMeResponse


class RefreshRequest(BaseModel):
    # Optional: cookie-auth clients send no body (the refresh token rides in the
    # httpOnly cookie); Bearer/API clients send it here.
    refresh_token: str | None = None


class RegisterOrgRequest(BaseModel):
    """Creates a new organization + first admin user in one step."""
    org_name: str
    org_slug: str
    industry: IndustryLiteral
    admin_name: str
    admin_email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v):
        errors = validate_password_strength(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v

    @field_validator("org_slug")
    @classmethod
    def valid_slug(cls, v):
        import re
        if not re.match(r"^[a-z0-9][a-z0-9-]{2,49}$", v):
            raise ValueError("Slug must be 3-50 chars, lowercase letters, numbers, hyphens only.")
        return v


class PasswordResetRequest(BaseModel):
    email: EmailStr
    org_slug: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v):
        errors = validate_password_strength(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v
