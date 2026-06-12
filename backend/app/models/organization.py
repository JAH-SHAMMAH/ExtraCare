from sqlalchemy import Column, String, Boolean, Enum, JSON, Text, Integer, DateTime
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
import enum


class IndustryType(str, enum.Enum):
    SCHOOL = "school"
    HOSPITAL = "hospital"
    BUSINESS = "business"
    HYBRID = "hybrid"  # Multiple modules enabled


class SubscriptionTier(str, enum.Enum):
    FREE = "free"          # 1 module, up to 10 users
    PRO = "pro"            # up to 2 modules, up to 50 users
    ENTERPRISE = "enterprise"  # all modules, unlimited users, all features
    # Legacy tier values kept so old rows still deserialise. Not offered in
    # new signups — the canonical plans are free/pro/enterprise.
    STARTER = "starter"
    GROWTH = "growth"


class Organization(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    The core multi-tenant unit. Each org is fully isolated.
    Every query in the system is scoped by org_id.
    """
    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)  # used in subdomain: slug.extracare.app
    industry = Column(Enum(IndustryType), nullable=False, default=IndustryType.BUSINESS)
    subscription_tier = Column(Enum(SubscriptionTier), nullable=False, default=SubscriptionTier.FREE)

    # Contact & branding
    logo_url = Column(String(500), nullable=True)
    favicon_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#16a34a")  # hex (now green instead of blue)
    secondary_color = Column(String(7), default="#f0fdf4")  # hex (light green)
    branding_settings = Column(JSON, default=dict)  # {display_name, accent_color, font_family, etc}
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    country = Column(String(100), nullable=True)
    timezone = Column(String(50), default="Africa/Lagos")
    currency = Column(String(10), default="NGN")

    # Feature flags — which modules are enabled
    modules_enabled = Column(JSON, default=list)  # e.g. ["hr", "payroll", "school"]

    # Per-tenant feature overrides. Keys are flag names, values are bool.
    # Merged on top of the plan's default_features at read time — so a free
    # tenant can still have `ai_assistant: true` toggled on for a beta. Never
    # consult this column directly; go through core.features.resolve_features.
    features = Column(JSON, default=dict)

    # Limits
    max_users = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Subscription metadata
    stripe_customer_id = Column(String(255), nullable=True)
    subscription_expires_at = Column(String(50), nullable=True)

    # Settings JSON blob (org-specific config)
    settings = Column(JSON, default=dict)

    # Onboarding state. Progression: modules → users → first_action → done.
    # `onboarding_completed` is derived from `onboarding_completed_at is not None`
    # so the two never drift. Step is advanced by the onboarding service only
    # after the backend verifies the underlying condition (modules chosen,
    # second user invited, primary record created).
    onboarding_step = Column(String(32), nullable=False, default="modules")
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    users = relationship("User", back_populates="organization", lazy="dynamic")
    roles = relationship("Role", back_populates="organization", lazy="dynamic")
    audit_logs = relationship("AuditLog", back_populates="organization", lazy="dynamic")
