"""Narrow the student role to explicit student-only scopes

Revision ID: 121_narrow_student_role_scopes
Revises: 120_add_section_id_to_timetable
Create Date: 2026-08-12 10:00:00.000000

The student role currently holds broad scopes like school:cbt:read, which via
the scope hierarchy grants access to admin CBT surfaces (Manage CBT, Results,
Interventions, Live Classes). This migration narrows the student role to
explicit, student-only scopes that don't bleed into admin interfaces:

  OLD: school:cbt:read (unlocks admin surfaces)
  NEW: school:cbt:sit (sit assigned exams only, not manage/create)

Similar to migration 118 (teacher RBAC narrowing), this is a backfill to apply
the narrowed preset to existing roles. Existing orgs keep whatever was seeded,
which for the student role was broad scopes. This migration fixes it.

Only the STUDENT role (by slug) is affected. Individual student user records
and the students table are unchanged — this is a role-level change only, safe
to run on production without per-student review.
"""
from alembic import op
import sqlalchemy as sa


revision = "121_narrow_student_role_scopes"
down_revision = "120_add_section_id_to_timetable"
branch_labels = None
depends_on = None


# The student role slug (single record per org, but we match by slug).
STUDENT_SLUG = "student"

# New narrow permissions: explicit student-only scopes, no admin leaks.
NEW_PERMISSIONS = [
    # Core personal read-only access (own records only, enforced server-side)
    "school:timetable:read",        # My Timetable
    "school:library:read",          # My Library (catalogue + own loans, backend scoped)
    "school:reports:read",          # My Report Card (own only, published-only, backend scoped)
    "school:classroom:read",        # My Assignments/Classwork (own only, backend scoped)
    "school:journals:read",         # My Photo Journals
    "school:lessons:read",          # Assigned Lesson Content
    # Student-specific engagement (distinct from admin/teacher scopes)
    "school:cbt:sit",               # NEW: Sit assigned exams (not manage/create)
    "school:clubs:read",            # Browse clubs and enroll
    "school:feedback:read",         # Submit feedback (write-action gated server-side)
    "school:voting:submit",         # NEW: Vote/rate for teacher (cast own vote only)
]

OLD_PERMISSIONS = [
    # Previous broad scopes (many leak to admin surfaces)
    "school:cbt:read",              # ← Unlocks admin CBT (Manage, Results, Interventions, Live Classes)
    "school:cbt:write",             # ← Already being removed
    "school:classroom:read",        # ← Already OK but will stay
    "school:classroom:write",       # ← Already being removed
    "school:clubs:read",            # ← Already OK
    "school:journals:read",         # ← Already OK
    "school:lessons:read",          # ← Already OK
    "school:library:read",          # ← Already OK
    "school:reports:read",          # ← Already OK (with new backend gates)
]


def _apply(permissions: list[str]) -> None:
    """Apply permissions to student role (by slug, not filtered by is_system)."""
    roles = sa.table("roles",
        sa.column("slug", sa.String),
        sa.column("permissions", sa.JSON),
    )
    stmt = roles.update().where(
        roles.c.slug == STUDENT_SLUG
    ).values(permissions=permissions)
    op.execute(stmt)


def upgrade() -> None:
    _apply(NEW_PERMISSIONS)


def downgrade() -> None:
    _apply(OLD_PERMISSIONS)
