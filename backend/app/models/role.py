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


# ── Fine-grained school scopes (Phase 7 RBAC) ────────────────────────────────
#
# The school module is gated by per-feature scopes of the form
# `school:<feature>:<action>`. Trusted roles still carry the broad `school:read`
# / `school:write` grants, and the scope hierarchy in `User.has_permission`
# makes a broad grant satisfy every fine-grained child (so `school:read`
# automatically covers `school:students:read`). This keeps the rollout
# non-breaking while letting low-trust roles (student, parent) hold ONLY the
# narrow scopes for the features they may touch.
#
# `school_admin:*` is a DELIBERATELY separate namespace for school back-office
# administration (bulk SMS, transport, tuckshop). Because it is not under the
# `school` namespace, a broad `school:read`/`school:write` does NOT grant it —
# that is precisely how teachers are kept out of admin tooling while still
# holding broad teaching access.
#
# Feature scopes introduced as the "Coming Soon" placeholders are built out:
#   Batch 1 (People & HR):
#     • school:parents:read / :write  — Parents Directory. NOT added to any
#       preset on purpose: the broad-grant hierarchy means org_admin (school:*),
#       manager/teacher/staff/viewer (school:read[/write]) reach it automatically,
#       while student/parent (narrow scopes only) never do — so a guardian PII
#       directory stays staff-only with zero preset churn.
#     • Staff Assessment / Talent Pool reuse `hr:write` (org_admin + manager),
#       keeping confidential HR admin on the existing hr:* lattice rather than
#       growing a parallel one (teachers hold only the self-service `hr:read`).

# Self-service scopes a STUDENT may hold. No roster/PII scopes — a student
# reaches only their own academic surface. Their personal data (timetable,
# attendance %) is served ownership-safe by /me/contexts with no school scope.
SCHOOL_STUDENT_PERMISSIONS = [
    "school:reports:read",      # own report card / grades
    "school:lessons:read",      # published lesson material
    "school:classroom:read", "school:classroom:write",  # eClassroom: view + submit
    "school:cbt:read", "school:cbt:write",              # CBT: sit tests + submit
    "school:clubs:read",        # browse clubs
    "school:library:read",      # browse catalogue + own loans
    "school:journals:read",     # class photo journals
]

# Self-service scopes a PARENT may hold. Read-only over their CHILD's surface;
# ownership is enforced per-record (a parent passing another child's id is
# rejected). Fees/payments stay on the separate `payments` namespace.
SCHOOL_PARENT_PERMISSIONS = [
    "school:attendance:read",   # child attendance (ownership-scoped)
    "school:reports:read",      # child grades / report card (ownership-scoped)
    "school:journals:read",     # child class journals
    "school:feedback:read",     # raise & view feedback
    "payments:read",            # view & pay child's outstanding fees
]

# Payments namespace (school fees / Paystack) is gated separately from
# `school:*` by the school_payments router (payments:read|write|reconcile).
# Grant it to the roles that actually transact:
#   - org_admin: full, including reconcile (the Principal also acts as bursar)
#   - manager:   read + write (record/initiate), no reconcile
#   - parent:    read (view & pay their child's outstanding fees)
# A dedicated Accountant role with reconcile-only finance scope is a planned
# follow-up (needs role-switcher support); until then admins reconcile.
SCHOOL_PERMISSION_PRESETS = {
    # `payment_gateways:*` is a DELIBERATELY SEPARATE namespace from `payments:*`
    # (not `payments:gateways:*`): managing live gateway API secrets is org_admin-only,
    # and a `payments:gateways:write` sub-scope would be auto-satisfied by any
    # `payments:write` holder (accountant/manager) via the scope hierarchy. Keeping
    # it its own namespace makes "org_admin only" real. See ENCRYPTION_SERVICE_SPEC.md §9.
    "org_admin": _dedupe(CORE_ADMIN_PERMISSIONS + ["school:*", "school_admin:*", "payments:*", "payment_gateways:read", "payment_gateways:write", "store:*", "medical:*", "wallet:*"]),
    "manager": _dedupe(CORE_MANAGER_PERMISSIONS + ["school:read", "school:write", "school_admin:read", "school_admin:write", "payments:read", "payments:write", "wallet:spend"]),
    # Teacher holds broad school read/write (covers every fine-grained school
    # feature via the hierarchy) but NOT `school_admin:*` or `payments:*`, so
    # bulk SMS / transport / tuckshop / fee administration stay out of reach.
    # `users:read` is RETAINED for the Messenger "new conversation" picker.
    # `hr:read` is a self-service marker (My HRM Info / My Leave nav); HR
    # mutations + the admin HR dashboard stay on users:*/hr:write, which the
    # teacher does NOT hold.
    "teacher": _dedupe(["users:read", "school:read", "school:write", "analytics:read", "hr:read"]),
    # Frontline staff (e.g. tuckshop till) hold the dedicated, constrained
    # `wallet:spend` so they can ring up spends in real time — but NOT cash
    # movement or general ledger posting.
    "staff": _dedupe(CORE_STAFF_PERMISSIONS + ["school:read", "wallet:spend"]),
    # School health officer. Holds ONLY the confidential `medical:*` surface (+
    # self-service hr:read for their own leave) — deliberately NO `school:*`, so
    # a nurse sees Medicals and nothing else of the school back-office, and no
    # general staff/teacher can read medical records.
    "nurse": _dedupe(["medical:read", "medical:write", "hr:read"]),
    # School bursar/accountant. Segregation of duties: holds payments:write
    # (draft) AND payments:post (post to the ledger) — but the payroll two-person
    # rule (approved_by != created_by) still blocks self-approving a run. Scoped
    # to finance only (no school:*), like the nurse is to medical.
    "accountant": _dedupe(["payments:read", "payments:write", "payments:post", "store:sell", "wallet:spend", "hr:read"]),
    # School-store cashier / front-desk till operator. Mirrors the tuckshop-till
    # pattern above (narrow `wallet:spend`): holds the dedicated `store:sell` so
    # they can ring up + void store sales at the POS, plus `payments:read` to see
    # the catalog and sales list — but NOT `payments:post`, so a junior cashier
    # canNOT approve payroll, waive fees (discounts), or post general ledger
    # entries. Least-privilege for daily till staff.
    "cashier": _dedupe(["payments:read", "store:sell"]),
    # Facility / maintenance staff. Scoped to the Facility Management module only
    # via the fine-grained `school_admin:facility:*` child scope (org_admin +
    # manager reach it automatically through their broad school_admin:read/write
    # grant). `school:read` lets the module's user/entity pickers work. NO other
    # back-office access — like the nurse is to medical.
    "facilities": _dedupe(["school_admin:facility:read", "school_admin:facility:write", "school:read"]),
    "student": _dedupe(SCHOOL_STUDENT_PERMISSIONS),
    "parent": _dedupe(SCHOOL_PARENT_PERMISSIONS),
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
SCHOOL_ROLE_SLUGS = ("org_admin", "manager", "teacher", "staff", "nurse", "accountant", "cashier", "student", "parent", "viewer")


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
