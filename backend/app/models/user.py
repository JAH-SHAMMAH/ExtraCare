from sqlalchemy import Column, String, Boolean, Enum, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.models.role import user_roles
import enum


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"       # invited but not accepted yet
    LOCKED = "locked"         # too many failed logins


class User(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "users"

    # Identity
    email = Column(String(320), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=True)  # nullable for SSO-only users
    avatar_url = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    department = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)
    employee_id = Column(String(100), nullable=True)  # custom org employee code

    # Auth
    status = Column(Enum(UserStatus), default=UserStatus.PENDING, nullable=False, index=True)
    is_superadmin = Column(Boolean, default=False)  # platform-level superadmin
    email_verified = Column(Boolean, default=False)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    failed_login_attempts = Column(String(10), default="0")
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)  # IPv6 max 45 chars

    # Password reset
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)

    # Invite flow
    invite_token = Column(String(255), nullable=True)
    invite_expires = Column(DateTime(timezone=True), nullable=True)
    invited_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Profile extras
    bio = Column(Text, nullable=True)
    preferences = Column(JSON, default=dict)  # theme, locale, notification prefs

    # Tenant FK
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Composite unique: email is unique per org (same email can exist in diff orgs)
    # Enforced at application level + partial unique index

    # Relationships
    organization = relationship("Organization", back_populates="users")
    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.actor_id", lazy="raise")

    @property
    def primary_role(self) -> str:
        if self.is_superadmin:
            return "super_admin"
        if self.roles:
            return self.roles[0].slug
        return "viewer"

    @property
    def permissions(self) -> set[str]:
        perms = set()
        for role in self.roles:
            perms.update(role.permissions or [])
        return perms

    def has_permission(self, permission: str) -> bool:
        if self.is_superadmin:
            return True
        perms = self.permissions
        if "*" in perms:
            return True
        if permission in perms:
            return True
        parts = permission.split(":")
        namespace = parts[0]
        # Namespace wildcard: "school:*" covers "school:read" AND "school:students:read".
        if f"{namespace}:*" in perms:
            return True
        # Scope hierarchy: a broad two-part grant covers its fine-grained
        # children, so holding "school:read" satisfies "school:students:read"
        # and "school:write" satisfies "school:grades:write". This lets the
        # fine-grained permission rollout stay non-breaking — roles that still
        # carry the broad scope keep reaching every sub-scoped endpoint.
        if len(parts) == 3:
            return f"{namespace}:{parts[2]}" in perms
        return False

    def has_module_permission(self, namespace: str, action: str = "read") -> bool:
        """True if the user can perform `action` ANYWHERE in a module namespace.

        Used by the router-level module gate: a caller may enter the school
        module if they hold the broad `school:read`, the wildcard `school:*`,
        OR any fine-grained child such as `school:cbt:read`. The per-endpoint
        PermissionChecker still enforces the specific feature scope afterwards —
        this only decides whether the module door opens at all.
        """
        if self.is_superadmin:
            return True
        perms = self.permissions
        if "*" in perms or f"{namespace}:*" in perms or f"{namespace}:{action}" in perms:
            return True
        prefix = f"{namespace}:"
        suffix = f":{action}"
        return any(p.startswith(prefix) and p.endswith(suffix) for p in perms)
