from sqlalchemy import Column, String, JSON, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship

from app.core.workspace import WorkspaceType, workspace_for
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin

# Many-to-many: users <-> roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


# System-level permissions (fine-grained)
#
# Scopes used by the backend routers & frontend PermissionGate:
#   users, roles, settings, audit_logs      - platform/admin
#   school, hospital, business              - vertical module CRUD
#   payroll, finance                        - sensitive business sub-scopes
#   imports, analytics                      - cross-module tooling
#
# `namespace:*` acts as a wildcard for that namespace (see User.has_permission).
CORE_ADMIN_PERMISSIONS = [
    "users:read", "users:write", "users:delete",
    "roles:read", "roles:write",
    "settings:read", "settings:write",
    "audit_logs:read",
    "imports:read", "imports:write", "imports:rollback",
    "analytics:read",
    "hr:read", "hr:write",
]

CORE_MANAGER_PERMISSIONS = [
    "users:read", "users:write",
    "imports:read", "imports:write",
    "analytics:read",
    "hr:read", "hr:write",
]

CORE_STAFF_PERMISSIONS = [
    "users:read",
    "analytics:read",
    "hr:read",
]

CORE_VIEWER_PERMISSIONS = [
    "users:read",
    "analytics:read",
]


def _dedupe(perms: list[str]) -> list[str]:
    return list(dict.fromkeys(perms))


# Payments namespace (school fees / Paystack) is gated separately from
# `school:*` by the school_payments router (payments:read|write|reconcile).
# Grant it to the roles that actually transact:
#   - org_admin: full, including reconcile (the Principal also acts as bursar)
#   - manager:   read + write (record/initiate), no reconcile
#   - parent:    read (view & pay their child's outstanding fees)
# A dedicated Accountant role with reconcile-only finance scope is a planned
# follow-up (needs role-switcher support); until then admins reconcile.
SCHOOL_PERMISSION_PRESETS = {
    "org_admin": _dedupe(CORE_ADMIN_PERMISSIONS + ["school:*", "payments:*"]),
    "manager": _dedupe(CORE_MANAGER_PERMISSIONS + ["school:read", "school:write", "payments:read", "payments:write"]),
    # Phase 1 (2026-06-07): dropped `hr:read` — it gated nothing (HR endpoints
    # use users:read/users:write) and no frontend surface checked it. `users:read`
    # is RETAINED: the teacher-reachable Messenger "new conversation" picker lists
    # users via GET /users (users:read). Removing it would break teacher direct
    # messaging — see the Phase 1 report. `analytics:read` removal is Phase 2.
    "teacher": ["users:read", "school:read", "school:write", "analytics:read"],
    "staff": _dedupe(CORE_STAFF_PERMISSIONS + ["school:read"]),
    "student": ["school:read"],
    "parent": _dedupe(["school:read", "payments:read"]),
    "viewer": _dedupe(CORE_VIEWER_PERMISSIONS + ["school:read"]),
}

BUSINESS_PERMISSION_PRESETS = {
    "org_admin": _dedupe(CORE_ADMIN_PERMISSIONS + ["business:*", "payroll:*", "finance:*", "inventory:*", "crm:*"]),
    "manager": _dedupe(CORE_MANAGER_PERMISSIONS + ["business:read", "business:write", "payroll:read", "finance:read", "inventory:read", "crm:read"]),
    "hr_officer": _dedupe(CORE_MANAGER_PERMISSIONS + ["business:read", "business:write", "payroll:read", "payroll:write"]),
    "accountant": _dedupe(CORE_VIEWER_PERMISSIONS + ["business:read", "finance:*", "payroll:read"]),
    "employee": ["business:read", "hr:read"],
    "staff": _dedupe(CORE_STAFF_PERMISSIONS + ["business:read"]),
    "viewer": _dedupe(CORE_VIEWER_PERMISSIONS + ["business:read"]),
}

HOSPITAL_PERMISSION_PRESETS = {
    "org_admin": _dedupe(CORE_ADMIN_PERMISSIONS + ["hospital:*"]),
    "manager": _dedupe(CORE_MANAGER_PERMISSIONS + ["hospital:read", "hospital:write"]),
    "doctor": ["users:read", "hospital:read", "hospital:write", "analytics:read", "hr:read"],
    "nurse": ["users:read", "hospital:read", "hospital:write", "hr:read"],
    "staff": _dedupe(CORE_STAFF_PERMISSIONS + ["hospital:read"]),
    "viewer": _dedupe(CORE_VIEWER_PERMISSIONS + ["hospital:read"]),
}


def permission_presets_for_industry(industry: str | None) -> dict[str, list[str]]:
    """Workspace-scoped system roles for an organisation industry."""
    workspace = workspace_for(industry)
    if workspace.type == WorkspaceType.SCHOOL:
        return SCHOOL_PERMISSION_PRESETS
    if workspace.type == WorkspaceType.HOSPITAL:
        return HOSPITAL_PERMISSION_PRESETS
    if workspace.type == WorkspaceType.BUSINESS:
        return BUSINESS_PERMISSION_PRESETS

    merged: dict[str, list[str]] = {"super_admin": ["*"]}
    for presets in (SCHOOL_PERMISSION_PRESETS, HOSPITAL_PERMISSION_PRESETS, BUSINESS_PERMISSION_PRESETS):
        for slug, perms in presets.items():
            merged[slug] = _dedupe(merged.get(slug, []) + perms)
    return merged


def role_slugs_for_industry(industry: str | None) -> tuple[str, ...]:
    return tuple(slug for slug in permission_presets_for_industry(industry).keys() if slug != "super_admin")


# Legacy import alias. New code should call permission_presets_for_industry so
# default roles are scoped to the tenant workspace.
PERMISSION_PRESETS = permission_presets_for_industry("hybrid")

# Roles auto-created for every school-industry org at registration + by seed.
# Ordered for stable UI listing (admins first, students/parents last).
SCHOOL_ROLE_SLUGS = ("org_admin", "manager", "teacher", "staff", "student", "parent", "viewer")


class Role(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Org-scoped roles. System roles ship per workspace type.
    Orgs can create custom roles with granular permissions.
    """
    __tablename__ = "roles"

    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False)  # e.g. "org_admin", "teacher", "doctor"
    description = Column(String(500), nullable=True)
    permissions = Column(JSON, default=list)  # ["users:read", "school:write", ...]
    is_system = Column(Boolean, default=False)  # system roles can't be deleted
    color = Column(String(7), default="#0057c2")  # for UI badge

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    organization = relationship("Organization", back_populates="roles")
    users = relationship("User", secondary=user_roles, back_populates="roles")
