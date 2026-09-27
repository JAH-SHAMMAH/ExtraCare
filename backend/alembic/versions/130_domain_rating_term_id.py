"""StudentDomainRating.term -> term_id: the last string-matched term

Revision ID: 130_domain_rating_term_id
Revises: 129_score_provenance
Create Date: 2026-09-27

`student_domain_ratings.term` was a free-text String(50). Its own schema example
was "Term 1" — the exact drifted string that silenced every parent's report card
when the configured terms were Autumn/Spring/Summer. It was the last place in the
codebase where a term was matched by name rather than by id.

Converted while the table held ZERO rows, which is the cheapest this will ever
be. Once real EYFS ratings accumulate, the same conversion becomes a data
migration with an unresolvable-name problem and no good answer.

REFUSES TO RUN IF THE TABLE IS NOT EMPTY. A non-empty table means this database
has ratings whose term is a name, and there is no safe automatic answer for a
name that matches no AcademicTerm: dropping the row loses a real assessment of a
real child, and guessing a term is worse. Better to stop and be told than to
improvise. Production was verified empty before this shipped.

The unique constraint and the index both move with the column — a constraint left
on the dropped column would not survive, and one left naming `term` would not be
recreated, so both are rebuilt explicitly.
"""
import sqlalchemy as sa
from alembic import op

revision = "130_domain_rating_term_id"
down_revision = "129_score_provenance"
branch_labels = None
depends_on = None

TABLE = "student_domain_ratings"


def upgrade() -> None:
    conn = op.get_bind()

    # Offline `--sql` rendering cannot read, and this migration's safety depends on
    # reading. Emit the DDL and skip the guard, so the shape stays reviewable
    # without a database while a real run still refuses a non-empty table.
    offline = op.get_context().as_sql
    if not offline:
        n = conn.execute(sa.text(f"SELECT count(*) FROM {TABLE}")).scalar()
        if n:
            raise RuntimeError(
                f"{TABLE} holds {n} row(s). This migration converts a free-text term "
                f"to a term_id FK and will not guess at term names. Resolve each "
                f"row's term to an AcademicTerm id by hand, or clear the table, then "
                f"re-run."
            )

    op.drop_constraint("uq_student_domain_rating", TABLE, type_="unique")
    op.drop_index("ix_student_domain_ratings_term", table_name=TABLE)

    op.add_column(TABLE, sa.Column("term_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_student_domain_ratings_term_id_academic_terms", TABLE, "academic_terms",
        ["term_id"], ["id"], ondelete="CASCADE",
    )
    # NOT NULL only after the column exists: on an empty table there is nothing to
    # backfill, and the guard above guarantees it is empty.
    op.alter_column(TABLE, "term_id", nullable=False)
    op.drop_column(TABLE, "term")

    op.create_index("ix_student_domain_ratings_term_id", TABLE, ["term_id"])
    op.create_unique_constraint(
        "uq_student_domain_rating", TABLE, ["student_id", "term_id", "domain_id"])
    op.create_index("ix_student_domain_ratings_term", TABLE, ["org_id", "term_id"])


def downgrade() -> None:
    op.drop_index("ix_student_domain_ratings_term", table_name=TABLE)
    op.drop_constraint("uq_student_domain_rating", TABLE, type_="unique")
    op.drop_index("ix_student_domain_ratings_term_id", table_name=TABLE)

    op.add_column(TABLE, sa.Column("term", sa.String(length=50), nullable=True))
    # A term NAME cannot be recovered from an id without a lookup, so the down
    # migration fills it from academic_terms where it can. Rows whose term was
    # deleted come back with NULL rather than a fabricated name.
    op.execute(sa.text(f"""
        UPDATE {TABLE} r SET term = t.name
        FROM academic_terms t WHERE t.id = r.term_id
    """))
    op.alter_column(TABLE, "term", nullable=False)

    op.drop_constraint("fk_student_domain_ratings_term_id_academic_terms", TABLE, type_="foreignkey")
    op.drop_column(TABLE, "term_id")

    op.create_unique_constraint(
        "uq_student_domain_rating", TABLE, ["student_id", "term", "domain_id"])
    op.create_index("ix_student_domain_ratings_term", TABLE, ["org_id", "term"])
