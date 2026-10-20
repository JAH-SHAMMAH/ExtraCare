"""teaching_assignments: teacher x class x subject

Revision ID: 151_teaching_assignments
Revises: 150_answer_option_type
"""
import sqlalchemy as sa
from alembic import op

revision = "151_teaching_assignments"
down_revision = "150_answer_option_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "teaching_assignments" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "teaching_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("class_id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "teacher_id", "class_id", "subject_id", name="uq_teaching_assignment"),
    )
    op.create_index("ix_teaching_assignments_teacher_id", "teaching_assignments", ["teacher_id"])
    op.create_index("ix_teaching_assignments_class_id", "teaching_assignments", ["class_id"])
    op.create_index("ix_teaching_assignments_subject_id", "teaching_assignments", ["subject_id"])
    op.create_index("ix_teaching_assignments_org_id", "teaching_assignments", ["org_id"])
    op.create_index("ix_teaching_assignments_org_teacher", "teaching_assignments", ["org_id", "teacher_id"])


def downgrade() -> None:
    op.drop_table("teaching_assignments")
