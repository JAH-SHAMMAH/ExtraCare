"""
Workspace Type Engine & Organization Type Configuration
========================================================

Centralized registry defining what each organization type (School, Hospital, Business, Hybrid)
can access, including modules, roles, features, and UI configuration.

This is the single source of truth for workspace isolation — all permission checks,
module gates, and UI rendering decisions flow through these definitions.

Usage:
  workspace = workspace_for(org.industry)
  if "school" in workspace.primary_modules:
      # render school-specific UI
"""

from enum import Enum
from typing import Set, Optional, Dict, Any, Iterable
from dataclasses import dataclass, field


class WorkspaceType(str, Enum):
    """Organization industry vertical."""

    SCHOOL = "school"
    HOSPITAL = "hospital"
    BUSINESS = "business"
    HYBRID = "hybrid"  # Multi-vertical support (can access all types)


PRIMARY_WORKSPACE_MODULE: dict[WorkspaceType, str] = {
    WorkspaceType.SCHOOL: "school",
    WorkspaceType.HOSPITAL: "hospital",
    WorkspaceType.BUSINESS: "business",
}

# Permission namespaces that represent vertical product surfaces. Shared ERP
# namespaces such as users/settings/audit/analytics stay outside this map.
WORKSPACE_PERMISSION_SCOPES: dict[str, WorkspaceType] = {
    "school": WorkspaceType.SCHOOL,
    "school_admin": WorkspaceType.SCHOOL,  # school back-office (sms/transport/tuckshop)
    # Confidential student health data. DELIBERATELY its own namespace (like
    # school_admin) so the broad `school:read` hierarchy does NOT reach it —
    # only roles explicitly granted `medical:*` (org_admin, nurse) can see it.
    "medical": WorkspaceType.SCHOOL,
    # Dedicated, self-limiting capability: `wallet:spend` lets till staff draw a
    # student's OWN wallet down to income (no-overdraw, period-locked) and nothing
    # else — it cannot move cash, post invoices, or create arbitrary entries.
    "wallet": WorkspaceType.SCHOOL,
    "hospital": WorkspaceType.HOSPITAL,
    "business": WorkspaceType.BUSINESS,
    "payroll": WorkspaceType.BUSINESS,
    "finance": WorkspaceType.BUSINESS,
    "inventory": WorkspaceType.BUSINESS,
    "crm": WorkspaceType.BUSINESS,
}

# Module aliases let a route or feature ask for a sub-capability while still
# being governed by the correct workspace. The database can continue storing
# the primary module key only ("school", "business", "hospital").
MODULE_WORKSPACE_SCOPES: dict[str, WorkspaceType] = {
    "school": WorkspaceType.SCHOOL,
    "attendance": WorkspaceType.SCHOOL,
    "behaviour": WorkspaceType.SCHOOL,
    "cbt": WorkspaceType.SCHOOL,
    "classroom": WorkspaceType.SCHOOL,
    "clubs": WorkspaceType.SCHOOL,
    "exams": WorkspaceType.SCHOOL,
    "fees": WorkspaceType.SCHOOL,
    "feedback": WorkspaceType.SCHOOL,
    "journals": WorkspaceType.SCHOOL,
    "library": WorkspaceType.SCHOOL,
    "parents": WorkspaceType.SCHOOL,
    "payments": WorkspaceType.SCHOOL,
    "results": WorkspaceType.SCHOOL,
    "sms": WorkspaceType.SCHOOL,
    "subjects": WorkspaceType.SCHOOL,
    "teachers": WorkspaceType.SCHOOL,
    "timetable": WorkspaceType.SCHOOL,
    "transport": WorkspaceType.SCHOOL,
    "tuckshop": WorkspaceType.SCHOOL,
    "hospital": WorkspaceType.HOSPITAL,
    "admissions": WorkspaceType.HOSPITAL,
    "appointments": WorkspaceType.HOSPITAL,
    "emr": WorkspaceType.HOSPITAL,
    "billing": WorkspaceType.HOSPITAL,
    "doctors": WorkspaceType.HOSPITAL,
    "lab": WorkspaceType.HOSPITAL,
    "nurses": WorkspaceType.HOSPITAL,
    "patients": WorkspaceType.HOSPITAL,
    "pharmacy": WorkspaceType.HOSPITAL,
    "prescriptions": WorkspaceType.HOSPITAL,
    "wards": WorkspaceType.HOSPITAL,
    "business": WorkspaceType.BUSINESS,
    "customers": WorkspaceType.BUSINESS,
    "crm": WorkspaceType.BUSINESS,
    "departments": WorkspaceType.BUSINESS,
    "employees": WorkspaceType.BUSINESS,
    "expenses": WorkspaceType.BUSINESS,
    "finance": WorkspaceType.BUSINESS,
    "inventory": WorkspaceType.BUSINESS,
    "invoices": WorkspaceType.BUSINESS,
    "payroll": WorkspaceType.BUSINESS,
    "pos": WorkspaceType.BUSINESS,
    "procurement": WorkspaceType.BUSINESS,
    "projects": WorkspaceType.BUSINESS,
    "sales": WorkspaceType.BUSINESS,
}


@dataclass
class WorkspaceDefinition:
    """Defines what an organization type can access and how."""

    type: WorkspaceType
    label: str  # Human-readable: "School", "Hospital", "Business", "Multi-Industry"

    # Module configuration
    primary_modules: Set[str] = field(default_factory=set)  # e.g. {"school", "behaviour", "cbt"}
    secondary_modules: Set[str] = field(default_factory=set)  # e.g. {"library", "transport"}

    # UI configuration
    dashboard_type: str = "generic"  # "school", "hospital", "business", "generic"
    sidebar_sections: Optional[Dict[str, Any]] = None  # Can override sidebar structure

    # Role configuration
    role_types: Set[str] = field(default_factory=set)  # {"admin", "manager", "teacher", "student"}
    supported_role_types: Dict[str, list] = field(default_factory=dict)  # Role → Permissions

    # Feature flags
    features: Set[str] = field(default_factory=set)  # {"sms", "attendance", "payroll"}

    # Metadata
    color: str = "#000000"  # For UI theming
    icon: str = "building"  # For UI theming
    description: str = ""

    @property
    def all_modules(self) -> Set[str]:
        """All modules available to this workspace type."""
        return self.primary_modules | self.secondary_modules

    def has_module(self, module_name: str) -> bool:
        """Check if module is accessible in this workspace."""
        return module_name in self.all_modules

    def has_feature(self, feature_name: str) -> bool:
        """Check if feature is available in this workspace."""
        return feature_name in self.features

    def has_role(self, role_slug: str) -> bool:
        """Check if role exists in this workspace."""
        return role_slug in self.role_types


# ============================================================================
# Workspace Definitions Registry
# ============================================================================


WORKSPACE_REGISTRY: Dict[WorkspaceType, WorkspaceDefinition] = {
    WorkspaceType.SCHOOL: WorkspaceDefinition(
        type=WorkspaceType.SCHOOL,
        label="School",
        description="Educational institutions: primary & secondary schools, colleges",
        color="#059669",  # Green (updated from indigo)
        icon="graduation-cap",
        primary_modules={
            "school",  # Students, classes, timetable
            "behaviour",  # Pastoral care
            "cbt",  # Computer-based testing (exams)
            "classroom",  # eClassroom assignments
            "clubs",  # Clubs & activities
            "feedback",  # Student feedback
            "journals",  # Class journals
            "tuckshop",  # School shop
            "payments",  # School payments portal
            "fees",  # Student fees
        },
        secondary_modules={
            "library",  # Book management
            "transport",  # Student transport
            "sms",  # Parent/student communications
            "hr",  # Staff management
            "leave",  # Leave requests
            "analytics",  # Reporting & insights
        },
        dashboard_type="school",
        role_types={
            "org_admin",  # Org administrator
            "manager",  # Admin manager
            "teacher",  # Teaching staff
            "staff",  # Non-teaching staff
            "student",  # Students
            "parent",  # Parents/guardians
            "viewer",
        },
        features={
            "sms",  # Bulk SMS campaigns
            "attendance",  # Daily attendance tracking
            "grades",  # Grade management
            "timetable",  # Class scheduling
            "assignments",  # Online assignments
            "payments",  # Payment processing
        },
    ),
    WorkspaceType.HOSPITAL: WorkspaceDefinition(
        type=WorkspaceType.HOSPITAL,
        label="Hospital",
        description="Healthcare institutions: hospitals, clinics, medical centers",
        color="#DC2626",  # Red
        icon="heart",
        primary_modules={
            "hospital",  # Patient records (EMR-lite)
        },
        secondary_modules={
            "appointments",  # Doctor scheduling
            "emr",  # Electronic medical records
            "billing",  # Hospital billing
            "lab",  # Lab test tracking
            "pharmacy",  # Pharmacy operations
            "wards",  # Wards and admissions
            "hr",  # Staff management
            "leave",  # Leave requests
            "analytics",  # Reporting & insights
        },
        dashboard_type="hospital",
        role_types={
            "org_admin",  # Org administrator
            "manager",  # Admin manager
            "doctor",  # Medical doctors
            "nurse",  # Nursing staff
            "staff",  # Admin/support staff
            "viewer",
        },
        features={
            "appointments",  # Appointment scheduling
            "medical_records",  # Patient EMR
            "prescriptions",  # Prescription management
            "lab_tests",  # Lab test tracking
        },
    ),
    WorkspaceType.BUSINESS: WorkspaceDefinition(
        type=WorkspaceType.BUSINESS,
        label="Business",
        description="Companies & enterprises: corporations, SMEs, NGOs",
        color="#059669",  # Green
        icon="briefcase",
        primary_modules={
            "business",  # Core business module (employees, departments)
        },
        secondary_modules={
            "payroll",  # Payroll management
            "inventory",  # Stock management
            "finance",  # Revenue and expenses
            "invoices",  # Customer invoices
            "crm",  # Customer relationship
            "procurement",  # Purchasing workflows
            "projects",  # Project tracking
            "hr",  # HR administration
            "leave",  # Leave management
            "analytics",  # Business analytics
        },
        dashboard_type="business",
        role_types={
            "org_admin",  # Org administrator
            "manager",  # Department manager
            "employee",  # Regular employee
            "hr_officer",  # HR department
            "accountant",  # Finance/accounting
            "staff",
            "viewer",
        },
        features={
            "payroll",  # Payroll processing
            "leave_requests",  # Employee leave
            "inventory",  # Stock tracking
            "invoices",  # Customer invoices
        },
    ),
    WorkspaceType.HYBRID: WorkspaceDefinition(
        type=WorkspaceType.HYBRID,
        label="Multi-Industry",
        description="Organizations serving multiple verticals (limited support, marked for deprecation)",
        color="#7C3AED",  # Purple
        icon="layers",
        primary_modules={
            "school",
            "hospital",
            "business",
        },
        secondary_modules={
            "library",
            "transport",
            "appointments",
            "emr",
            "lab",
            "pharmacy",
            "wards",
            "payroll",
            "inventory",
            "finance",
            "invoices",
            "procurement",
            "projects",
            "sms",
            "hr",
            "leave",
            "analytics",
        },
        dashboard_type="generic",
        role_types={
            "admin",
            "org_admin",
            "manager",
            "teacher",
            "student",
            "parent",
            "doctor",
            "nurse",
            "employee",
            "hr_officer",
            "accountant",
            "staff",
        },
        features={
            "sms",
            "attendance",
            "grades",
            "timetable",
            "appointments",
            "medical_records",
            "prescriptions",
            "payroll",
            "leave_requests",
            "inventory",
            "invoices",
        },
    ),
}


# ============================================================================
# Public API Functions
# ============================================================================


def workspace_for(org_industry: Optional[str]) -> WorkspaceDefinition:
    """
    Lookup workspace definition by organization industry type.

    Args:
        org_industry: The organization's industry type (from org.industry field)

    Returns:
        WorkspaceDefinition for the industry, or hybrid if not found

    Examples:
        workspace = workspace_for("school")
        workspace = workspace_for(org.industry)
    """
    if not org_industry:
        return WORKSPACE_REGISTRY[WorkspaceType.HYBRID]

    try:
        workspace_type = WorkspaceType(org_industry)
        return WORKSPACE_REGISTRY.get(workspace_type, WORKSPACE_REGISTRY[WorkspaceType.HYBRID])
    except (ValueError, KeyError):
        return WORKSPACE_REGISTRY[WorkspaceType.HYBRID]


def workspace_type_for(org_industry: Optional[str]) -> WorkspaceType:
    """Resolve an industry string to a WorkspaceType, defaulting defensively."""
    return workspace_for(org_industry).type


def primary_module_for_workspace(workspace_type: WorkspaceType | str) -> str | None:
    """Primary module key for a single-vertical workspace."""
    if isinstance(workspace_type, str):
        try:
            workspace_type = WorkspaceType(workspace_type)
        except ValueError:
            return None
    return PRIMARY_WORKSPACE_MODULE.get(workspace_type)


def module_workspace(module_name: str) -> WorkspaceType | None:
    """Return the owning workspace for a module/sub-module key."""
    return MODULE_WORKSPACE_SCOPES.get(module_name)


def module_allowed_by_workspace(industry: Optional[str], module_name: str) -> bool:
    """Whether a module belongs in the organisation's workspace type."""
    workspace = workspace_for(industry)
    if workspace.type == WorkspaceType.HYBRID:
        return module_name in MODULE_WORKSPACE_SCOPES or module_name in workspace.all_modules
    owner = module_workspace(module_name)
    if owner is not None:
        return owner == workspace.type
    return workspace.has_module(module_name)


def effective_modules_for(
    industry: Optional[str],
    configured_modules: Iterable[str] | None,
) -> list[str]:
    """Configured modules after applying the workspace boundary.

    This is intentionally non-destructive: it never mutates
    Organization.modules_enabled. It only answers "what should be active for
    this organisation right now?" so legacy rows with stray module keys stop
    leaking into routing, JWT claims, and sidebar rendering.
    """
    configured = list(configured_modules or [])
    if not configured:
        return []

    workspace = workspace_for(industry)
    if workspace.type == WorkspaceType.HYBRID:
        return sorted({m for m in configured if m in MODULE_WORKSPACE_SCOPES or m in workspace.all_modules})

    allowed = {
        module
        for module in configured
        if module_allowed_by_workspace(industry, module)
    }
    return sorted(allowed)


def effective_modules_for_org(org) -> list[str]:
    """Organization-aware wrapper that works with SQLAlchemy models."""
    industry = org.industry.value if getattr(org, "industry", None) is not None else None
    return effective_modules_for(industry, getattr(org, "modules_enabled", None))


def is_module_enabled_for_org(org, module_name: str) -> bool:
    """True when the module is configured and belongs to the org workspace."""
    configured = set(getattr(org, "modules_enabled", None) or [])
    if module_name in configured:
        return module_allowed_by_workspace(
            org.industry.value if getattr(org, "industry", None) is not None else None,
            module_name,
        )

    owner = module_workspace(module_name)
    if owner is None:
        return module_name in effective_modules_for_org(org)

    primary = primary_module_for_workspace(owner)
    return bool(
        primary
        and primary in configured
        and module_allowed_by_workspace(
            org.industry.value if getattr(org, "industry", None) is not None else None,
            primary,
        )
    )


def permission_scope_allowed_for_org(org, permission: str) -> bool:
    """Prevent legacy cross-vertical permissions from authorising access."""
    namespace = permission.split(":", 1)[0]
    owner = WORKSPACE_PERMISSION_SCOPES.get(namespace)
    if owner is None:
        return True
    workspace = workspace_for(
        org.industry.value if getattr(org, "industry", None) is not None else None
    )
    return workspace.type == WorkspaceType.HYBRID or workspace.type == owner


def is_module_in_workspace(workspace: WorkspaceDefinition, module_name: str) -> bool:
    """
    Check if a module is available in a workspace.

    Args:
        workspace: The workspace definition
        module_name: Module key to check (e.g., "school", "payroll")

    Returns:
        True if module is in primary or secondary modules

    Examples:
        if is_module_in_workspace(workspace, "payroll"):
            # show payroll UI
    """
    return workspace.has_module(module_name)


def is_role_in_workspace(workspace: WorkspaceDefinition, role_slug: str) -> bool:
    """
    Check if a role exists in a workspace.

    Args:
        workspace: The workspace definition
        role_slug: Role key to check (e.g., "teacher", "doctor")

    Returns:
        True if role is defined for this workspace

    Examples:
        if is_role_in_workspace(workspace, "teacher"):
            # allow assigning teacher role
    """
    return workspace.has_role(role_slug)


def is_feature_enabled_in_workspace(workspace: WorkspaceDefinition, feature_name: str) -> bool:
    """
    Check if a feature is available in a workspace.

    Args:
        workspace: The workspace definition
        feature_name: Feature key to check (e.g., "sms", "payroll")

    Returns:
        True if feature is enabled for this workspace

    Examples:
        if is_feature_enabled_in_workspace(workspace, "sms"):
            # show SMS menu option
    """
    return workspace.has_feature(feature_name)


def workspace_label(org_industry: Optional[str]) -> str:
    """Get human-readable label for workspace type."""
    workspace = workspace_for(org_industry)
    return workspace.label


def get_all_workspace_types() -> Dict[str, WorkspaceDefinition]:
    """Get all available workspace types (useful for admin UI)."""
    return {
        wt.value: workspace_def
        for wt, workspace_def in WORKSPACE_REGISTRY.items()
    }


def validate_module_for_workspace(
    workspace: WorkspaceDefinition,
    module_name: str,
) -> tuple[bool, Optional[str]]:
    """
    Validate if a module can be enabled for a workspace.

    Returns:
        (is_valid, error_message)

    Examples:
        valid, msg = validate_module_for_workspace(workspace, "payroll")
        if not valid:
            raise ValueError(msg)
    """
    if workspace.has_module(module_name):
        return True, None

    # Check if it's a sub-feature that shouldn't be toggled independently
    SUB_FEATURES_ONLY = {
        "attendance",
        "grades",
        "timetable",
        "appointments",
        "emr",
    }

    if module_name in SUB_FEATURES_ONLY:
        return False, f"'{module_name}' is included with its primary module"

    return False, f"Module '{module_name}' not available for {workspace.label} workspace"


def validate_role_for_workspace(
    workspace: WorkspaceDefinition,
    role_slug: str,
) -> tuple[bool, Optional[str]]:
    """
    Validate if a role can be assigned in a workspace.

    Returns:
        (is_valid, error_message)
    """
    if workspace.has_role(role_slug):
        return True, None

    return False, (
        f"Role '{role_slug}' does not exist in {workspace.label} workspace. "
        f"Valid roles: {', '.join(sorted(workspace.role_types))}"
    )


# ============================================================================
# Feature Flag Helpers
# ============================================================================


def workspace_isolation_enabled(
    enable_flag: bool = True,
    org_override: Optional[bool] = None,
) -> bool:
    """
    Check if workspace isolation should be used.

    This allows for:
    1. Global feature flag (WORKSPACE_ISOLATION_ENABLED env var)
    2. Per-org override (stored in org.workspace_isolation_enabled)

    Args:
        enable_flag: Global feature flag value
        org_override: Per-org override (None = use global)

    Returns:
        Whether workspace isolation is active

    Examples:
        if workspace_isolation_enabled(os.getenv("WORKSPACE_ISOLATION_ENABLED")):
            # use new workspace system
        else:
            # use legacy code paths
    """
    if org_override is not None:
        return org_override
    return enable_flag


# ============================================================================
# Migration Helpers
# ============================================================================


def get_default_modules_for_industry(industry: str) -> list[str]:
    """
    Get default modules when an org registers for an industry type.

    This is used during signup to seed the org.modules_enabled list.
    """
    workspace = workspace_for(industry)
    if workspace.type == WorkspaceType.HYBRID:
        return ["business", "hospital", "school"]
    primary = primary_module_for_workspace(workspace.type)
    return [primary] if primary else []


def get_default_roles_for_industry(industry: str) -> list[str]:
    """
    Get default role slugs to create when an org registers for an industry type.

    This ensures only workspace-appropriate roles exist on signup.
    """
    workspace = workspace_for(industry)
    return sorted(list(workspace.role_types))
