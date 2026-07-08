"""Create cbt_question_bank (reusable CBT Question Bank)

Revision ID: 037_add_cbt_question_bank
Revises: 036_add_force_password_change
Create Date: 2026-07-08 10:00:00.000000

Additive + reversible. Phase A of the CBT upgrade: a reusable, categorised
question bank (subject + topic + difficulty) that tests are composed from. Enum
values are member NAMES per the project convention (see questiontype).
"""

from alembic import op
import sqlalchemy as sa


revision = "037_add_cbt_question_bank"
down_revision = "036_add_force_password_change"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cbt_question_bank",
        sa.Column("subject_id", sa.String(length=36), nullable=True),
        sa.Column("topic", sa.String(length=150), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.Enum("MCQ", "TRUE_FALSE", "SHORT_ANSWER", "LONG_ANSWER", name="questiontype"), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name=op.f("fk_cbt_question_bank_subject_id_subjects")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_cbt_question_bank_created_by_users")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_cbt_question_bank_org_id_organizations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cbt_question_bank")),
    )
    with op.batch_alter_table("cbt_question_bank", schema=None) as b:
        b.create_index(b.f("ix_cbt_question_bank_id"), ["id"], unique=False)
        b.create_index(b.f("ix_cbt_question_bank_org_id"), ["org_id"], unique=False)
        b.create_index(b.f("ix_cbt_question_bank_subject_id"), ["subject_id"], unique=False)
        b.create_index(b.f("ix_cbt_question_bank_topic"), ["topic"], unique=False)
        b.create_index("ix_cbt_question_bank_subject_org", ["subject_id", "org_id"], unique=False)


def downgrade() -> None:
    op.drop_table("cbt_question_bank")
