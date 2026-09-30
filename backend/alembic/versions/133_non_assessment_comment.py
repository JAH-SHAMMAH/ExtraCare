"""Non Assessment Comment: custom comment slots on the report card

Revision ID: 133_non_assessment_comment
Revises: 132_cbt_exam_term_id
Create Date: 2026-09-30

`report_comment_types` already lets an administrator define named comment slots —
it is the "Comment" tab, built long ago. Nothing could ever hold a VALUE for one:
`student_report_comments.kind` is a two-value set, head | pc, and only those two
have entry and a place on the card. Every other slot an admin created was inert.

This gives those slots somewhere to store a comment.

    report_comment_types.admin_only   who may write the slot
    student_report_comments.comment_type_id   which slot a row is for

OWNERSHIP IS THE TWO RULES THAT ALREADY EXIST, not a third. A slot is
PC-teacher-writable by default (like `pc`), or admin-only when flagged (like
`head`). `_gate_comment_access` reads the flag instead of testing for the literal
string "head".

WHY TWO PARTIAL INDEXES RATHER THAN ONE CONSTRAINT. The obvious move — add
comment_type_id to the existing unique constraint — is a trap this codebase has
already documented once, in SubjectReportComment's docstring: Postgres treats
NULLs as DISTINCT in a unique index, so the head and pc rows, which carry NULL
there, would stop being unique against each other and a pupil could silently
collect two School Head comments.

So the rows are split by the thing that would have been NULL, and each half gets
an index that cannot see the other:

  built-ins  (comment_type_id IS NULL)     unique on (org, student, term, sub, kind)
  slots      (comment_type_id IS NOT NULL) unique on (org, student, term, sub, type)

The predicates are exact complements, so no row is in both and none is in
neither. `kind` is deliberately ABSENT from the slot key: including it would let
two rows share a slot by varying kind, which is two comments in one box on the
card.

`kind` stays NOT NULL. Custom rows carry the literal 'custom', meaning "the slot
is in comment_type_id". Making `kind` nullable instead would reintroduce exactly
the NULL-distinctness problem in the built-in index.

Verified before writing: 0 rows in student_report_comments, so there is nothing
to backfill and neither index can be blocked by existing data. 0 slots are
configured, so nothing changes for anyone until an admin creates one.
"""
import sqlalchemy as sa
from alembic import op

revision = "133_non_assessment_comment"
down_revision = "132_cbt_exam_term_id"
branch_labels = None
depends_on = None

TABLE = "student_report_comments"
BUILTIN_IX = "uq_student_report_comment_builtin"
SLOT_IX = "uq_student_report_comment_slot"
OLD_UQ = "uq_student_report_comment"


def upgrade() -> None:
    op.add_column("report_comment_types", sa.Column(
        "admin_only", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column(TABLE, sa.Column("comment_type_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_student_report_comments_comment_type", TABLE, "report_comment_types",
        ["comment_type_id"], ["id"], ondelete="CASCADE",
    )

    # The old constraint covered every row; the two below cover the same rows
    # between them, and keep the built-ins behaving exactly as they did.
    op.drop_constraint(OLD_UQ, TABLE, type_="unique")
    op.create_index(
        BUILTIN_IX, TABLE,
        ["org_id", "student_id", "term_id", "sub_term_id", "kind"],
        unique=True, postgresql_where=sa.text("comment_type_id IS NULL"),
    )
    op.create_index(
        SLOT_IX, TABLE,
        ["org_id", "student_id", "term_id", "sub_term_id", "comment_type_id"],
        unique=True, postgresql_where=sa.text("comment_type_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Custom-slot rows cannot survive: the single constraint below has no way to
    # tell two slots apart, so they would collide on (student, term, sub, kind).
    # Removed rather than collapsed into one another.
    op.execute(sa.text(f"DELETE FROM {TABLE} WHERE comment_type_id IS NOT NULL"))
    op.drop_index(SLOT_IX, table_name=TABLE)
    op.drop_index(BUILTIN_IX, table_name=TABLE)
    op.create_unique_constraint(
        OLD_UQ, TABLE, ["org_id", "student_id", "term_id", "sub_term_id", "kind"])
    op.drop_constraint("fk_student_report_comments_comment_type", TABLE, type_="foreignkey")
    op.drop_column(TABLE, "comment_type_id")
    op.drop_column("report_comment_types", "admin_only")
