"""CBTExam.term -> term_id: the column that feeds the freeze gate

Revision ID: 132_cbt_exam_term_id
Revises: 131_report_approval_term_id
Create Date: 2026-09-28

`cbt_exams.term` is free text, and it is the column the report freeze gate reads
through. `assessment_block_reason` resolves it with
`AcademicTerm.name == exam.term` and, when the spelling does not line up, returns
"No academic term named 'X' exists" — so a drifted name silently stops CBT scores
reaching Make Report. The model's own comment documented the drifted vocabulary
(`# e.g. "Term 1"`), and so did the exam form's placeholder, which is where the
'Term 1' values came from while the terms were Autumn/Spring/Summer.

120 rows at Fairview, all 'Autumn', all resolving, none NULL — verified before
this was written. As with migration 131 it resolves per-org and RAISES rather
than nulling a row it cannot convert, so a drifted exam is reported instead of
quietly losing which term it was sat in.

WHY ON DELETE SET NULL, NOT CASCADE. Migration 131 used CASCADE because a report
release is meaningless without the term it released. Here the term only TAGS a
sitting. Four foreign keys point AT cbt_exams.id — cbt_attempts (1,799 rows),
cbt_questions, cbt_interventions and grades.cbt_exam_id — and none of them
declare ON DELETE. So a CASCADE here would make deleting a term either fail with
an opaque foreign-key violation from a child table, or, if those children were
ever given CASCADE themselves, destroy 1,799 attempts as a side effect of an
admin tidying up a term list.

SET NULL leaves the exam intact and merely untagged, which is a state the product
already has a message for: `_feed_block_reason` says "Set a term on the exam
before sending results to the gradebook." Recoverable, and already explained.

A consequence worth naming: a term RENAME no longer strands these rows at all.
That was the whole failure mode — the exam kept a name the terms no longer used.
The term-delete guard still counts them, but as rows whose tag goes NULL rather
than rows whose name stops matching.

No unique constraint references `term`, so unlike 131 there is none to move.
"""
import sqlalchemy as sa
from alembic import op

revision = "132_cbt_exam_term_id"
down_revision = "131_report_approval_term_id"
branch_labels = None
depends_on = None

TABLE = "cbt_exams"


def upgrade() -> None:
    conn = op.get_bind()
    offline = op.get_context().as_sql

    op.add_column(TABLE, sa.Column("term_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_cbt_exams_term_id_academic_terms", TABLE, "academic_terms",
        ["term_id"], ["id"], ondelete="SET NULL",
    )

    if not offline:
        # Resolve within the org: term names are only unique per organisation.
        res = conn.execute(sa.text(f"""
            UPDATE {TABLE} e SET term_id = t.id
            FROM academic_terms t
            WHERE t.org_id = e.org_id AND t.name = e.term
        """))
        print(f"[132] resolved {res.rowcount} exam(s) to a term id")

        stranded = conn.execute(sa.text(f"""
            SELECT e.id, e.title, e.term FROM {TABLE} e
            WHERE e.term IS NOT NULL AND e.term_id IS NULL
        """)).fetchall()
        if stranded:
            detail = ", ".join(f"{row[0]} {row[1]!r} term={row[2]!r}"
                               for row in stranded[:10])
            raise RuntimeError(
                f"{len(stranded)} CBT exam(s) name a term that does not exist in "
                f"their organisation, so they cannot be converted: {detail}. These "
                f"exams are ALREADY not reaching Make Report — the sync blocks them "
                f"with 'No academic term named ... exists' — and the fix is the same "
                f"one it asks for: create the missing academic term, or correct the "
                f"term on the exam. Then re-run. Nulling them here would throw away "
                f"the only record of which term the sitting belonged to."
            )

    op.create_index("ix_cbt_exams_term_id", TABLE, ["term_id"])
    op.drop_column(TABLE, "term")


def downgrade() -> None:
    op.drop_index("ix_cbt_exams_term_id", table_name=TABLE)
    op.add_column(TABLE, sa.Column("term", sa.String(length=50), nullable=True))
    # A name is recoverable from the id by lookup. An exam whose term was deleted
    # (SET NULL) comes back NULL rather than with a fabricated name.
    op.execute(sa.text(f"""
        UPDATE {TABLE} e SET term = t.name
        FROM academic_terms t WHERE t.id = e.term_id
    """))
    op.drop_constraint("fk_cbt_exams_term_id_academic_terms", TABLE, type_="foreignkey")
    op.drop_column(TABLE, "term_id")
