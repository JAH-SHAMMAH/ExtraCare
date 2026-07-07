"""Create exams table + grades.exam_id (manual gradebook)

Revision ID: 034_add_exams
Revises: 033_add_subject_fields
Create Date: 2026-07-07 11:00:00.000000

Additive + reversible. Backs the Exams feature: an Exam is a manual sitting for a
class + subject; entered marks land as Grade rows tagged with exam_id (so exam
results flow into the existing report-card). Enum values are member NAMES, per the
project convention (see gradestatus in the baseline).
"""

from alembic import op
import sqlalchemy as sa


revision = "034_add_exams"
down_revision = "033_add_subject_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("exam_type", sa.String(length=30), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=True),
        sa.Column("class_id", sa.String(length=36), nullable=True),
        sa.Column("term", sa.String(length=50), nullable=True),
        sa.Column("session_year", sa.String(length=20), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("start_time", sa.String(length=10), nullable=True),
        sa.Column("end_time", sa.String(length=10), nullable=True),
        sa.Column("total_marks", sa.Float(), nullable=False),
        sa.Column("pass_marks", sa.Float(), nullable=False),
        sa.Column("status", sa.Enum("SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED", name="examsittingstatus"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name=op.f("fk_exams_subject_id_subjects")),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], name=op.f("fk_exams_class_id_school_classes")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_exams_created_by_users")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_exams_org_id_organizations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exams")),
    )
    with op.batch_alter_table("exams", schema=None) as b:
        b.create_index(b.f("ix_exams_id"), ["id"], unique=False)
        b.create_index(b.f("ix_exams_org_id"), ["org_id"], unique=False)
        b.create_index(b.f("ix_exams_subject_id"), ["subject_id"], unique=False)
        b.create_index(b.f("ix_exams_class_id"), ["class_id"], unique=False)

    # exam_id column + index only. The FK is declared on the ORM model (and honoured
    # by the test schema built from metadata); SQLite doesn't enforce FKs by default,
    # and adding one to an existing table needs a fragile batch table-rebuild — not
    # worth it for a nullable back-reference.
    op.add_column("grades", sa.Column("exam_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_grades_exam_id"), "grades", ["exam_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_grades_exam_id"), table_name="grades")
    op.drop_column("grades", "exam_id")
    op.drop_table("exams")
