"""Add admissions & enrollment tables (Batch 2)

Revision ID: 004_add_admissions_enrollment
Revises: 003_add_people_hr_development
Create Date: 2026-06-21 00:30:00.000000

Purely additive and reversible. Creates the student-lifecycle tables:
admission_applications, entrance_exams, entrance_exam_results,
promotion_records, transfer_records. Touches no existing table or row.
"""

from alembic import op
import sqlalchemy as sa


revision = "004_add_admissions_enrollment"
down_revision = "003_add_people_hr_development"
branch_labels = None
depends_on = None


def _ts_cols():
    return (
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "admission_applications",
        *_ts_cols(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("guardian_name", sa.String(200), nullable=True),
        sa.Column("guardian_phone", sa.String(50), nullable=True),
        sa.Column("guardian_email", sa.String(320), nullable=True),
        sa.Column("applying_for_class_id", sa.String(36), nullable=True),
        sa.Column("applying_for_level", sa.String(80), nullable=True),
        sa.Column("source", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="enquiry"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("admitted_student_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_admission_applications"),
        sa.ForeignKeyConstraint(["applying_for_class_id"], ["school_classes.id"], ondelete="SET NULL", name="fk_admission_applications_applying_for_class_id_school_classes"),
        sa.ForeignKeyConstraint(["admitted_student_id"], ["students.id"], ondelete="SET NULL", name="fk_admission_applications_admitted_student_id_students"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_admission_applications_created_by_users"),
    )
    op.create_index("ix_admission_applications_id", "admission_applications", ["id"])
    op.create_index("ix_admission_applications_org_id", "admission_applications", ["org_id"])
    op.create_index("ix_admission_applications_org_status", "admission_applications", ["org_id", "status"])

    op.create_table(
        "entrance_exams",
        *_ts_cols(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("subject", sa.String(120), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_entrance_exams"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_entrance_exams_created_by_users"),
    )
    op.create_index("ix_entrance_exams_id", "entrance_exams", ["id"])
    op.create_index("ix_entrance_exams_org_id", "entrance_exams", ["org_id"])
    op.create_index("ix_entrance_exams_org_date", "entrance_exams", ["org_id", "exam_date"])

    op.create_table(
        "entrance_exam_results",
        *_ts_cols(),
        sa.Column("exam_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=True),
        sa.Column("candidate_name", sa.String(200), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_entrance_exam_results"),
        sa.ForeignKeyConstraint(["exam_id"], ["entrance_exams.id"], ondelete="CASCADE", name="fk_entrance_exam_results_exam_id_entrance_exams"),
        sa.ForeignKeyConstraint(["application_id"], ["admission_applications.id"], ondelete="SET NULL", name="fk_entrance_exam_results_application_id_admission_applications"),
    )
    op.create_index("ix_entrance_exam_results_id", "entrance_exam_results", ["id"])
    op.create_index("ix_entrance_exam_results_org_id", "entrance_exam_results", ["org_id"])
    op.create_index("ix_entrance_exam_results_exam_id", "entrance_exam_results", ["exam_id"])
    op.create_index("ix_entrance_exam_results_application_id", "entrance_exam_results", ["application_id"])
    op.create_index("ix_entrance_results_exam_org", "entrance_exam_results", ["exam_id", "org_id"])

    op.create_table(
        "promotion_records",
        *_ts_cols(),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("from_class_id", sa.String(36), nullable=True),
        sa.Column("to_class_id", sa.String(36), nullable=True),
        sa.Column("academic_year", sa.String(20), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="promoted"),
        sa.Column("promoted_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_promotion_records"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_promotion_records_student_id_students"),
        sa.ForeignKeyConstraint(["from_class_id"], ["school_classes.id"], ondelete="SET NULL", name="fk_promotion_records_from_class_id_school_classes"),
        sa.ForeignKeyConstraint(["to_class_id"], ["school_classes.id"], ondelete="SET NULL", name="fk_promotion_records_to_class_id_school_classes"),
        sa.ForeignKeyConstraint(["promoted_by"], ["users.id"], ondelete="SET NULL", name="fk_promotion_records_promoted_by_users"),
    )
    op.create_index("ix_promotion_records_id", "promotion_records", ["id"])
    op.create_index("ix_promotion_records_org_id", "promotion_records", ["org_id"])
    op.create_index("ix_promotion_records_student_id", "promotion_records", ["student_id"])
    op.create_index("ix_promotion_records_student_org", "promotion_records", ["student_id", "org_id"])

    op.create_table(
        "transfer_records",
        *_ts_cols(),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("transfer_type", sa.String(20), nullable=False, server_default="transfer_out"),
        sa.Column("destination_school", sa.String(200), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("transfer_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("processed_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_transfer_records"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_transfer_records_student_id_students"),
        sa.ForeignKeyConstraint(["processed_by"], ["users.id"], ondelete="SET NULL", name="fk_transfer_records_processed_by_users"),
    )
    op.create_index("ix_transfer_records_id", "transfer_records", ["id"])
    op.create_index("ix_transfer_records_org_id", "transfer_records", ["org_id"])
    op.create_index("ix_transfer_records_student_id", "transfer_records", ["student_id"])
    op.create_index("ix_transfer_records_student_org", "transfer_records", ["student_id", "org_id"])


def downgrade() -> None:
    for ix, tbl in [
        ("ix_transfer_records_student_org", "transfer_records"),
        ("ix_transfer_records_student_id", "transfer_records"),
        ("ix_transfer_records_org_id", "transfer_records"),
        ("ix_transfer_records_id", "transfer_records"),
    ]:
        op.drop_index(ix, table_name=tbl)
    op.drop_table("transfer_records")

    for ix in [
        "ix_promotion_records_student_org", "ix_promotion_records_student_id",
        "ix_promotion_records_org_id", "ix_promotion_records_id",
    ]:
        op.drop_index(ix, table_name="promotion_records")
    op.drop_table("promotion_records")

    for ix in [
        "ix_entrance_results_exam_org", "ix_entrance_exam_results_application_id",
        "ix_entrance_exam_results_exam_id", "ix_entrance_exam_results_org_id",
        "ix_entrance_exam_results_id",
    ]:
        op.drop_index(ix, table_name="entrance_exam_results")
    op.drop_table("entrance_exam_results")

    for ix in ["ix_entrance_exams_org_date", "ix_entrance_exams_org_id", "ix_entrance_exams_id"]:
        op.drop_index(ix, table_name="entrance_exams")
    op.drop_table("entrance_exams")

    for ix in ["ix_admission_applications_org_status", "ix_admission_applications_org_id", "ix_admission_applications_id"]:
        op.drop_index(ix, table_name="admission_applications")
    op.drop_table("admission_applications")
