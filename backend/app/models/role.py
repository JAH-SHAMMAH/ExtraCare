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
    # Core personal read-only access (own records only, enforced server-side via _scoped checks)
    "school:timetable:read",        # my timetable
    "school:library:read",          # browse catalogue + own loans
    "school:reports:read",          # own report card (published-only, enforced server-side)
    "school:classroom:read",        # own assignments / classwork (enforced server-side)
    "school:journals:read",         # own photo journals
    "school:lessons:read",          # assigned lesson material
    # Student-specific engagement (distinct from admin/teacher scopes)
    "school:cbt:sit",               # sit assigned exams (not manage/create)
    "school:clubs:read",            # browse clubs and enroll
    "school:feedback:read",         # submit feedback (write-action gated server-side)
    "school:voting:submit",         # vote/rate for teacher (cast own vote only)
]

# Self-service scopes a PARENT may hold. Read-only over their CHILD's surface;
# ownership is enforced per-record (a parent passing another child's id is
# rejected). Fees/payments stay on the separate `payments` namespace.
SCHOOL_PARENT_PERMISSIONS = [
    "school:attendance:read",   # child attendance (ownership-scoped in-endpoint)
    "school:reports:read",      # child grades / report card (ownership-scoped in-endpoint)
    "school:journals:read",     # child class journals
    "school:feedback:read",     # raise & view feedback
    # NOT `payments:read` -- that is the STAFF finance scope. It gates ~18 org-wide
    # routes (invoices, petty cash, store sales, wallet + cooperative summaries and
    # GL reconciliations), so granting it to parents exposed the school's books;
    # sensitive routes had been bumped to payments:WRITE one at a time to compensate,
    # which is a patch over a scope-design flaw and missed the rest.
    #
    # `payments:own:read` is a three-part scope, so User.has_permission resolves it
    # via its two-part parent: any staff holder of `payments:read` satisfies it
    # automatically (no staff regression), while a parent holding ONLY this does not
    # satisfy `payments:read`. Every org-wide finance route therefore closes at once,
    # and any route we overlook stays staff-only -- it fails closed, not open.
    "payments:own:read",        # view & pay THEIR OWN children's outstanding fees
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
    "manager": _dedupe(CORE_MANAGER_PERMISSIONS + ["school:read", "school:write", "school:cbt:manage", "school_admin:read", "school_admin:write", "payments:read", "payments:write", "wallet:spend"]),
    # Teacher = CLASSROOM tier: an ENUMERATED set of fine-grained scopes, never
    # the broad `school:read`/`school:write`.
    #
    # Why enumerated: the scope hierarchy (User.has_permission) makes a two-part
    # grant cover EVERY three-part child, so a teacher holding `school:write`
    # also held school:students:write, school:admissions:write,
    # school:timetable:write, school:library:write … i.e. the entire school
    # module minus `school_admin:*`. That is how a teacher could delete a pupil,
    # run promotions, edit the timetable structure and administer Voting. The
    # fine-grained rollout only becomes real once the broad grant is gone.
    #
    # Benchmarked against Educare's teacher nav: classroom + own-group pastoral +
    # self-service, and NO Students / Admissions / TimeTable-structure / Voting /
    # Library / Staff surfaces. Data scoping (own class, own subjects) is the
    # follow-up batch — this preset is the permission half.
    # `users:read` is RETAINED for the Messenger "new conversation" picker.
    # `hr:read` is a self-service marker (My HRM Info / My Leave nav); HR
    # mutations + the admin HR dashboard stay on users:*/hr:write, which the
    # teacher does NOT hold. `analytics:read` is deliberately DROPPED (the
    # Analytics dashboard is school-wide management reporting).
    "teacher": _dedupe([
        "users:read", "hr:read",
        # Lookups the classroom pickers/rosters need (read-only).
        "school:classes:read", "school:teachers:read", "school:students:read",
        "school:subjects:read", "school:timetable:read",
        # Marking + reporting.
        "school:grades:read", "school:grades:write",
        "school:exams:read", "school:exams:write",
        "school:reports:read", "school:reports:write",
        "school:attendance:read", "school:attendance:write",
        # Teaching tools: lesson plans, CBT (bank/tests/results), own eClassrooms.
        "school:lessons:read", "school:lessons:write",
        "school:cbt:read", "school:cbt:write", "school:cbt:manage",
        "school:classroom:read", "school:classroom:write",
        # Staff-only manage scope for the teacher's own eClassrooms. Deliberately
        # NOT school:classroom:write — students hold that to submit classwork, so
        # the schedule/go-live controls need a scope pupils never carry (the same
        # pattern as school:cbt:manage).
        "school:classroom:manage",
        # Pastoral for their own group: remarks/report/students + conduct points
        # and discipline logging. `school:pastoral:read` is the NON-boarding slice
        # — the hostel cluster stays on `school:hostel:*`, which teachers lack.
        "school:pastoral:read",
        "school:behaviour:read", "school:behaviour:write",
        "school:journals:read", "school:journals:write",
        "school:feedback:read", "school:feedback:write",
        "school:clubs:read", "school:clubs:write",
        # School calendar: teachers read the term's events/deadlines and author
        # their own (they did so under the old broad grant — this keeps it).
        "school:calendar:read", "school:calendar:write",
    ]),
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
    # `finance_admin:*` is the DEDICATED sensitive-finance namespace (Budget,
    # Payroll, Salary Advance, Bank Ledger, Statements, Broad View, Reports) —
    # the accountant is the primary finance operator, so holds read/write/post.
    "accountant": _dedupe(["payments:read", "payments:write", "payments:post",
                           "finance_admin:read", "finance_admin:write", "finance_admin:post",
                           "store:sell", "wallet:spend", "hr:read"]),
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

# ── Educare-parity role catalogue ────────────────────────────────────────────
# The full set of school roles so admins can assign the right one at account
# creation without adding roles later. Permission sets reuse the tiers above:
#   • _ADMIN  = full org admin (school:* + payments:* + admin)   — leadership
#   • _MGR    = senior admin (school:r/w + school_admin:r/w + payments:read + hr:r/w)
#   • _TCH    = teaching/academic — the ENUMERATED classroom scope set (NOT the
#               broad school:r/w). Every role on this tier is teacher-shaped, so
#               narrowing the tier closed the over-permissioning for all of them
#               at once (instructor, head_teacher, HODs, SPA, …).
#   • _MIN    = self-service only (own profile / leave)
# Specialist roles get narrow, function-specific scopes: exam_officer,
# admission_officer and guidance_counsellor each carry their own function's
# scopes instead of the classroom tier. Academic LEADERSHIP (head_teacher,
# academic_coordinator, HODs) sits on the classroom tier too — if a school needs
# them to see school-wide data, assign the manager tier explicitly rather than
# widening _TCH again.
_ADMIN = SCHOOL_PERMISSION_PRESETS["org_admin"]
_MGR = SCHOOL_PERMISSION_PRESETS["manager"]
_TCH = SCHOOL_PERMISSION_PRESETS["teacher"]
_MIN = ["hr:read"]   # own profile + My Leave / My HRM Info nav only

SCHOOL_PERMISSION_PRESETS.update({
    # Super User → the org's TOP tier: the `*` wildcard grants every permission in
    # the org (incl. finance_admin:* and payment_gateways), sitting genuinely above
    # org_admin (which holds an enumerated list, NOT `*`, and NOT finance_admin).
    "super_user": ["*"],
    # Principal / Head → Admin tier (same as org_admin): full school + fee
    # collection + user management, but NOT the sensitive finance_admin namespace.
    "principal": _ADMIN,
    "head": _ADMIN,
    # Senior administration → manager tier
    "vice_principal": _MGR,
    "deputy_head": _MGR,
    "administrative_coordinator": _MGR,
    # Head of Administration → manager tier PLUS sensitive-finance read/write (view
    # + draft Budget/Payroll/Salary-Advance/Ledger) — but NOT finance_admin:post,
    # so payroll approval / period lock / journal posting stay with the Accountant
    # (and the two-person rule). HR-adjacent; manager already includes hr:r/w.
    "head_of_administration": _dedupe(_MGR + ["finance_admin:read", "finance_admin:write"]),
    # Academic leadership / teaching → teacher tier
    "instructor": _TCH,
    "head_teacher": _TCH,
    "academic_coordinator": _TCH,
    "head_of_department_secondary": _TCH,
    "head_of_early_years": _TCH,
    "homeroom_coordinator": _TCH,
    "exam_subject_head": _TCH,
    # Narrowly scoped (gates split to match — see school.py / cbt.py): exams + CBT
    # admin + read-only reports/grades, plus the supporting rosters (students,
    # subjects, classes) their pickers need. NO broad school:write.
    "exam_officer": _dedupe([
        "school:exams:read", "school:exams:write",
        "school:cbt:read", "school:cbt:write",
        "school:cbt:manage",  # manage the CBT question bank / results without broad school:read/write
        "school:reports:read", "school:grades:read",
        "school:students:read", "school:subjects:read", "school:classes:read",
        "users:read", "hr:read",
    ]),
    "admission_officer": _dedupe([
        "school:admissions:read", "school:admissions:write",
        "school:students:read", "users:read", "hr:read",
    ]),
    "guidance_counsellor": _dedupe([
        "school:behaviour:read", "school:behaviour:write",
        "school:feedback:read", "school:feedback:write",
        "school:students:read", "users:read", "hr:read",
    ]),
    "spa_officer": _TCH,                      # SPA = Sports & Physical Activity
    "spa_manager": _TCH,
    # Specialist → narrow, function-specific
    "hr_manager": _dedupe(["hr:read", "hr:write", "users:read", "users:write", "analytics:read"]),
    "librarian": _dedupe(["school:library:read", "school:library:write", "users:read", "hr:read"]),
    "school_nurse": _dedupe(["medical:read", "medical:write", "hr:read"]),
    "facility_manager": _dedupe(["school_admin:facility:read", "school_admin:facility:write", "school:read", "hr:read"]),
    "frontdesk_officer": _dedupe(["users:read", "school:read", "payments:read", "store:sell", "hr:read"]),
    "storekeeper": _dedupe(["store:sell", "payments:read", "hr:read"]),
    # Support staff → self-service only
    "janitor": _MIN,
    "caregiver": _MIN,
    "maintenance_assistance": _MIN,
    "kitchen_assistant": _MIN,
    "assistant_chef": _MIN,
    "driver": _MIN,
    "head_of_kitchen": _MIN,
    "spa_attendant": _MIN,
})

# Display names where slug.title() would be wrong (acronyms, "of", parentheses).
ROLE_DISPLAY_NAMES = {
    "super_user": "Super User",
    "hr_manager": "HR Manager",
    "frontdesk_officer": "FrontDesk Officer",
    "spa_officer": "SPA Officer",
    "spa_attendant": "SPA Attendant",
    "spa_manager": "SPA Manager",
    "head_of_administration": "Head of Administration",
    "head_of_early_years": "Head of Early Years",
    "head_of_department_secondary": "Head of Department (Secondary)",
    "head_of_kitchen": "Head of Kitchen",
    "maintenance_assistance": "Maintenance Assistance",
}


def role_display_name(slug: str) -> str:
    """Human label for a preset slug (override table, else title-cased)."""
    return ROLE_DISPLAY_NAMES.get(slug, slug.replace("_", " ").title())


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
