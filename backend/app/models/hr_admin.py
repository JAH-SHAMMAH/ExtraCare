"""HR Admin managed lists (Phase 1) — the Educare 'Admin › Job' cluster.

One generic table backs the seven managed lists (Job Titles, Job Categories, Pay
Grades, Salary Components, Work Shifts, Employment Status, Working Tools), with a
``list_type`` discriminator. Deliberately light — name / code / description /
active — per the chosen 'managed lists only' scope; per-type fields (grade salary
bands, shift start/end times, earning-vs-deduction) are a later extension, not a
Phase-1 concern. Confidential HR admin: gated ``hr:write`` at the router."""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Integer, Boolean, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


# The HR admin managed lists: slug/key → human label. The router validates every
# ``list_type`` against this map, so an unknown list 404s rather than silently
# creating an orphan category. All share the one generic table (no migration to
# add a list) — Phase 1 shipped the Job cluster; Phase 2 added the reference lists.
HR_LIST_TYPES: dict[str, str] = {
    # Phase 1 — Job cluster
    "job_title": "Job Titles",
    "job_category": "Job Categories",
    "pay_grade": "Pay Grades",
    "salary_component": "Salary Components",
    "work_shift": "Work Shifts",
    "employment_status": "Employment Status",
    "working_tool": "Working Tools",
    # Phase 2 — Admin reference lists
    "competency": "Competency List",
    "qual_skill": "Qualification — Skills",
    "qual_education": "Qualification — Education",
    "qual_license": "Qualification — Licenses",
    "qual_language": "Qualification — Languages",
    "qual_membership": "Qualification — Memberships",
    "pension_fund": "Pension Fund Administrators",
    "hr_operation": "HR Operations",
    "contributory_leave": "Contributory Leave Allowance",
    "hr_department": "HR Departments",
    # Phase 2 — Discipline config (surfaced under the Discipline tab, not Admin)
    "disciplinary_type": "Disciplinary Types",
}


class HrManagedItem(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A single entry in one of the HR admin managed lists (see HR_LIST_TYPES)."""
    __tablename__ = "hr_managed_items"

    list_type = Column(String(40), nullable=False, index=True)   # job_title | pay_grade | ...
    name = Column(String(150), nullable=False)
    code = Column(String(40), nullable=True)                     # optional short code / abbreviation
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (Index("ix_hr_managed_items_org_type", "org_id", "list_type"),)
