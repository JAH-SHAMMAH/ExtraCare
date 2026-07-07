"""Create teacher_ratings table

Revision ID: 035_add_teacher_ratings
Revises: 034_add_exams
Create Date: 2026-07-07 12:00:00.000000

Additive + reversible. Backs the Teacher Ratings page (student→teacher 1–5 star
feedback), which called a /school/ratings API that was never built.
"""

from alembic import op
import sqlalchemy as sa


revision = "035_add_teacher_ratings"
down_revision = "034_add_exams"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teacher_ratings",
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("subject_id", sa.String(length=36), nullable=True),
        sa.Column("term", sa.String(length=50), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], name=op.f("fk_teacher_ratings_teacher_id_users")),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_teacher_ratings_student_id_students")),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name=op.f("fk_teacher_ratings_subject_id_subjects")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_teacher_ratings_org_id_organizations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teacher_ratings")),
    )
    with op.batch_alter_table("teacher_ratings", schema=None) as b:
        b.create_index(b.f("ix_teacher_ratings_id"), ["id"], unique=False)
        b.create_index(b.f("ix_teacher_ratings_org_id"), ["org_id"], unique=False)
        b.create_index(b.f("ix_teacher_ratings_teacher_id"), ["teacher_id"], unique=False)
        b.create_index(b.f("ix_teacher_ratings_student_id"), ["student_id"], unique=False)
        b.create_index("ix_teacher_ratings_teacher_org", ["teacher_id", "org_id"], unique=False)


def downgrade() -> None:
    op.drop_table("teacher_ratings")
