"""ReportApproval.term -> term_id: the column that caused the outage

Revision ID: 131_report_approval_term_id
Revises: 130_domain_rating_term_id
Create Date: 2026-09-27

`report_approvals.term` is free text, and it is THE column behind this morning's
incident: the approvals said 'Term 1' while the only selectable terms were
Autumn/Spring/Summer, so the parent report-card gate — which matches the workflow
row BY TERM NAME — found nothing and told every parent "this report has not been
published yet", for every term. The gate was right; the names had drifted.

Unlike migration 130's table, this one HAS live data (12 rows at Fairview), so it
cannot simply refuse a non-empty table. It resolves each row's name against
AcademicTerm within the same org and RAISES if any row cannot be resolved.

WHY RAISE RATHER THAN NULL OR DROP. An unresolvable row is precisely the drift
state this migration exists to end. Every one of these rows is a class's published
report: nulling its term would detach a release from the term it released, and
dropping it would un-publish a class's cards from under the parents reading them.
Neither is a decision a migration should make quietly. Fairview was verified first
— 12 rows, all 'Autumn', all resolving, none NULL.

The unique constraint moves with the column: (class_id, term) -> (class_id,
term_id). It is what makes "the stage" unambiguous for a class and term, and both
gates resolve a class's stage through it.

`term_id` stays NULLABLE, matching the column it replaces. The model allowed a
NULL term (an org-wide row), Postgres treats NULLs as distinct in a unique index,
and narrowing that here would be a behaviour change smuggled into a type change.
"""
import sqlalchemy as sa
from alembic import op

revision = "131_report_approval_term_id"
down_revision = "130_domain_rating_term_id"
branch_labels = None
depends_on = None

TABLE = "report_approvals"


def upgrade() -> None:
    conn = op.get_bind()
    offline = op.get_context().as_sql

    op.add_column(TABLE, sa.Column("term_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_report_approvals_term_id_academic_terms", TABLE, "academic_terms",
        ["term_id"], ["id"], ondelete="CASCADE",
    )

    if not offline:
        # Resolve within the org: term names are only unique per organisation.
        res = conn.execute(sa.text(f"""
            UPDATE {TABLE} r SET term_id = t.id
            FROM academic_terms t
            WHERE t.org_id = r.org_id AND t.name = r.term
        """))
        print(f"[131] resolved {res.rowcount} approval(s) to a term id")

        stranded = conn.execute(sa.text(f"""
            SELECT r.id, r.term, r.stage FROM {TABLE} r
            WHERE r.term IS NOT NULL AND r.term_id IS NULL
        """)).fetchall()
        if stranded:
            detail = ", ".join(f"{row[0]} term={row[1]!r} stage={row[2]!r}"
                               for row in stranded[:10])
            raise RuntimeError(
                f"{len(stranded)} report_approval row(s) name a term that does not "
                f"exist in their organisation, so they cannot be converted: {detail}. "
                f"This is the drift state this migration exists to end. Each row is a "
                f"class's report release — nulling its term would detach the release "
                f"from what it released, and deleting it would un-publish cards from "
                f"under the parents reading them. Create the missing AcademicTerm, or "
                f"correct the row's term, then re-run."
            )

    op.drop_constraint("uq_report_approval_class_term", TABLE, type_="unique")
    op.drop_column(TABLE, "term")
    op.create_index("ix_report_approvals_term_id", TABLE, ["term_id"])
    op.create_unique_constraint(
        "uq_report_approval_class_term", TABLE, ["class_id", "term_id"])


def downgrade() -> None:
    op.drop_constraint("uq_report_approval_class_term", TABLE, type_="unique")
    op.drop_index("ix_report_approvals_term_id", table_name=TABLE)

    op.add_column(TABLE, sa.Column("term", sa.String(length=40), nullable=True))
    # A name is recoverable from the id by lookup. A row whose term was deleted
    # comes back NULL rather than with a fabricated name.
    op.execute(sa.text(f"""
        UPDATE {TABLE} r SET term = t.name
        FROM academic_terms t WHERE t.id = r.term_id
    """))

    op.drop_constraint("fk_report_approvals_term_id_academic_terms", TABLE, type_="foreignkey")
    op.drop_column(TABLE, "term_id")
    op.create_unique_constraint(
        "uq_report_approval_class_term", TABLE, ["class_id", "term"])
