"""Pastoral Batch E: Discipline (sanction groups / actions / committees / cases)

Revision ID: 105_pastoral_discipline
Revises: 104_pastoral_hostel_life
Create Date: 2026-07-29 09:00:00.000000

Disciplinary Setup config (sanction groups, actions, committees + members) plus
the Behaviour & Sanction operational case record. Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "105_pastoral_discipline"
down_revision = "104_pastoral_hostel_life"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sanction_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sanction_groups_org_id", "sanction_groups", ["org_id"])

    op.create_table(
        "disciplinary_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sanction_group_id", sa.String(length=36), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="minor"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["sanction_group_id"], ["sanction_groups.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_disciplinary_actions_org_id", "disciplinary_actions", ["org_id"])
    op.create_index("ix_disciplinary_actions_sanction_group_id", "disciplinary_actions", ["sanction_group_id"])

    op.create_table(
        "disciplinary_committees",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_disciplinary_committees_org_id", "disciplinary_committees", ["org_id"])

    op.create_table(
        "disciplinary_committee_members",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("committee_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_label", sa.String(length=80), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["committee_id"], ["disciplinary_committees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "committee_id", "user_id", name="uq_committee_member"),
    )
    op.create_index("ix_disciplinary_committee_members_committee_id", "disciplinary_committee_members", ["committee_id"])
    op.create_index("ix_disciplinary_committee_members_user_id", "disciplinary_committee_members", ["user_id"])

    op.create_table(
        "student_disciplinary_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("committee_id", sa.String(length=36), nullable=True),
        sa.Column("action_id", sa.String(length=36), nullable=True),
        sa.Column("sanction_group_id", sa.String(length=36), nullable=True),
        sa.Column("offence", sa.Text(), nullable=True),
        sa.Column("sanction", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("case_date", sa.Date(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["committee_id"], ["disciplinary_committees.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["action_id"], ["disciplinary_actions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sanction_group_id"], ["sanction_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_disc_cases_student_id", "student_disciplinary_cases", ["student_id"])
    op.create_index("ix_student_disc_cases_student_org", "student_disciplinary_cases", ["student_id", "org_id"])
    op.create_index("ix_student_disc_cases_status_org", "student_disciplinary_cases", ["status", "org_id"])


def downgrade() -> None:
    op.drop_table("student_disciplinary_cases")
    op.drop_table("disciplinary_committee_members")
    op.drop_table("disciplinary_committees")
    op.drop_table("disciplinary_actions")
    op.drop_table("sanction_groups")
