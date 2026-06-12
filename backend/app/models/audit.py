from sqlalchemy import Column, String, JSON, ForeignKey, Text, Enum, Index
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin
import enum


class AuditAction(str, enum.Enum):
    # Auth
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    LOGIN_FAILED = "auth.login_failed"
    PASSWORD_RESET = "auth.password_reset"
    MFA_ENABLED = "auth.mfa_enabled"

    # Users
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_SUSPENDED = "user.suspended"
    USER_INVITED = "user.invited"
    ROLE_CHANGED = "user.role_changed"

    # Org
    ORG_UPDATED = "org.updated"
    ORG_INDUSTRY_CHANGED = "org.industry_changed"
    ORG_FEATURES_CHANGED = "org.features_changed"
    MODULE_ENABLED = "org.module_enabled"
    MODULE_DISABLED = "org.module_disabled"
    ORG_ONBOARDING_ADVANCED = "org.onboarding_advanced"

    # Billing
    PAYMENT_INITIATED = "billing.payment_initiated"
    PAYMENT_VERIFIED = "billing.payment_verified"
    PAYMENT_FAILED = "billing.payment_failed"
    SUBSCRIPTION_UPGRADED = "billing.subscription_upgraded"

    # Data
    RECORD_CREATED = "record.created"
    RECORD_UPDATED = "record.updated"
    RECORD_DELETED = "record.deleted"
    DATA_EXPORTED = "data.exported"
    DATA_IMPORTED = "data.imported"


class AuditLog(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Immutable audit trail. Never update or delete rows here.
    Used for security, compliance, and debugging.
    """
    __tablename__ = "audit_logs"

    action = Column(Enum(AuditAction), nullable=False, index=True)
    resource_type = Column(String(100), nullable=True)   # e.g. "User", "Student"
    resource_id = Column(String(36), nullable=True, index=True)
    resource_label = Column(String(255), nullable=True)  # human-readable: "Alexander Wright"

    # Who did it
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_email = Column(String(320), nullable=True)     # denormalized for log permanence
    actor_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # What changed (diff)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)

    # Severity
    severity = Column(String(20), default="info")  # info, warning, critical

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Activity feed and audit dashboards all hit this pattern:
    #   WHERE org_id = ? ORDER BY created_at DESC LIMIT N
    # A composite index on (org_id, created_at) lets the planner use an
    # index range scan instead of sorting every row in the tenant.
    __table_args__ = (
        Index("ix_audit_logs_org_created", "org_id", "created_at"),
    )

    # Relationships
    organization = relationship("Organization", back_populates="audit_logs", lazy="raise")
    actor = relationship("User", foreign_keys=[actor_id], lazy="raise")
