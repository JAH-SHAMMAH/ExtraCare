"""Narrow the teaching-tier system roles to the classroom scope set

Revision ID: 118_narrow_teaching_role_scopes
Revises: 117_user_is_seed_account
Create Date: 2026-08-04 10:00:00.000000

Role permissions live in the DB (roles.permissions), so changing the preset in
models/role.py only affects NEWLY created orgs. Existing orgs keep whatever was
seeded — which for every teaching role was the broad ["school:read",
"school:write", ...]. Because the scope hierarchy makes a two-part grant cover
every three-part child, that let teachers reach student deletion, promotions,
transfers, admissions, timetable structure, Voting and Library administration.

This backfills the shipped classroom preset onto the teaching-tier system roles
so the narrowing actually takes effect on existing deployments. The permission
list is written LITERALLY (a snapshot of this release) rather than imported from
app code, which is the usual data-migration trade-off: later preset changes get
their own migration or a POST /organizations/current/sync-roles call.

Matching is by SLUG, deliberately not filtered to is_system: these are preset
slugs, and a role carrying one is that role whoever created it (the report-demo
seed script, for instance, creates its roles with is_system=False — filtering
would silently skip exactly the accounts used to re-verify the fix). Every other
tier and every non-teaching slug is left exactly as it is. Downgrade restores the
previous broad grant.
"""
import json

from alembic import op
import sqlalchemy as sa


revision = "118_narrow_teaching_role_scopes"
down_revision = "117_user_is_seed_account"
branch_labels = None
depends_on = None


# Every role that sat on the shared teaching tier (_TCH in models/role.py).
TEACHING_SLUGS = (
    "teacher", "instructor", "head_teacher", "academic_coordinator",
    "head_of_department_secondary", "head_of_early_years", "homeroom_coordinator",
    "exam_subject_head", "spa_officer", "spa_manager",
)

NEW_PERMISSIONS = [
    "users:read", "hr:read",
    "school:classes:read", "school:teachers:read", "school:students:read",
    "school:subjects:read", "school:timetable:read",
    "school:grades:read", "school:grades:write",
    "school:exams:read", "school:exams:write",
    "school:reports:read", "school:reports:write",
    "school:attendance:read", "school:attendance:write",
    "school:lessons:read", "school:lessons:write",
    "school:cbt:read", "school:cbt:write", "school:cbt:manage",
    "school:classroom:read", "school:classroom:write", "school:classroom:manage",
    "school:pastoral:read",
    "school:behaviour:read", "school:behaviour:write",
    "school:journals:read", "school:journals:write",
    "school:feedback:read", "school:feedback:write",
    "school:clubs:read", "school:clubs:write",
    "school:calendar:read", "school:calendar:write",
]

OLD_PERMISSIONS = [
    "users:read", "school:read", "school:write", "school:cbt:manage",
    "analytics:read", "hr:read",
]


def _apply(permissions: list[str]) -> None:
    slugs = ", ".join(f"'{s}'" for s in TEACHING_SLUGS)
    op.execute(sa.text(
        f"UPDATE roles SET permissions = :perms WHERE slug IN ({slugs})"
    ).bindparams(perms=json.dumps(permissions)))


def upgrade() -> None:
    _apply(NEW_PERMISSIONS)


def downgrade() -> None:
    _apply(OLD_PERMISSIONS)
