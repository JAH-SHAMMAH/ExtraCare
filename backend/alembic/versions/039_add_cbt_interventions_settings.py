"""Create cbt_interventions + cbt_settings (CBT Phase C)

Revision ID: 039_cbt_phase_c
Revises: 038_normalize_term_values
Create Date: 2026-07-08 15:00:00.000000

Additive + reversible. Phase C: post-result intervention flags + org-level CBT
defaults. Enum values are member NAMES per the project convention.
"""

from alembic import op
import sqlalchemy as sa


revision = "039_cbt_phase_c"
down_revision = "038_normalize_term_values"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cbt_interventions",
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=True),
        sa.Column("attempt_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("OPEN", "IN_PROGRESS", "RESOLVED", name="interventionstatus"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("resolved_by", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_cbt_interventions_student_id_students")),
        sa.ForeignKeyConstraint(["exam_id"], ["cbt_exams.id"], name=op.f("fk_cbt_interventions_exam_id_cbt_exams")),
        sa.ForeignKeyConstraint(["attempt_id"], ["cbt_attempts.id"], name=op.f("fk_cbt_interventions_attempt_id_cbt_attempts")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_cbt_interventions_created_by_users")),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], name=op.f("fk_cbt_interventions_resolved_by_users")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_cbt_interventions_org_id_organizations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cbt_interventions")),
    )
    with op.batch_alter_table("cbt_interventions", schema=None) as b:
        b.create_index(b.f("ix_cbt_interventions_id"), ["id"], unique=False)
        b.create_index(b.f("ix_cbt_interventions_org_id"), ["org_id"], unique=False)
        b.create_index(b.f("ix_cbt_interventions_student_id"), ["student_id"], unique=False)
        b.create_index(b.f("ix_cbt_interventions_exam_id"), ["exam_id"], unique=False)

    op.create_table(
        "cbt_settings",
        sa.Column("default_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("default_pass_percentage", sa.Integer(), nullable=False),
        sa.Column("shuffle_default", sa.Boolean(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_cbt_settings_org_id_organizations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cbt_settings")),
        sa.UniqueConstraint("org_id", name=op.f("uq_cbt_settings_org_id")),
    )
    with op.batch_alter_table("cbt_settings", schema=None) as b:
        b.create_index(b.f("ix_cbt_settings_id"), ["id"], unique=False)
        b.create_index(b.f("ix_cbt_settings_org_id"), ["org_id"], unique=True)


def downgrade() -> None:
    op.drop_table("cbt_settings")
    op.drop_table("cbt_interventions")
