"""Subjects belong to a school section

Revision ID: 137_subject_section_scope
Revises: 136_attendance_unique_day
Create Date: 2026-10-03

`subjects` is flat and org-wide. Fairview's Educare keeps THREE separate subject
catalogues behind a "Select School of Subject" picker — Early Years (9), Primary
(21) and Secondary (49), 79 rows in total — and four titles appear in more than
one of them: Mathematics in all three, Geography, Music and Humanities in two.
A flat table cannot hold the same title twice, so deduped by name those 79 rows
collapse to 74 and the per-level identity is lost.

That is not hypothetical. One `Mathematics` row currently carries 540 Secondary
marks AND 360 enrolments spanning Primary and Secondary; under Educare those are
two different subjects. Every week the catalogue stays flat, more marks land on
rows that will eventually have to be split.

THIS MIGRATION IS SCHEMA ONLY. The backfill, the split of the two shared
subjects, six renames and 56 new rows are a DATA operation
(`scripts/scope_subjects_to_sections.py`) with a backup, a manifest and a
`--remove`, because splitting a subject means creating rows and repointing
others — work that belongs where it can be inspected and undone, not inside a
migration.

`section_id` IS NULLABLE HERE, and migration 138 tightens it to NOT NULL once
the script has run and verified zero nulls. A nullable scope invites reads of
the form "this section OR NULL", and treating NULL as a wildcard is how
cross-scope bleed gets reintroduced — the same reasoning migration 134 records
for `assessments.session_id`. It is nullable only for the window between the two
migrations.

ON DELETE RESTRICT, not CASCADE: deleting a section must not silently delete a
whole catalogue, and through it the marks that hang off those subjects.

THE UNIQUE CONSTRAINT IS NEW, not relaxed. `subjects` has never had a uniqueness
rule on its name — nothing stopped two identical subjects in one organisation,
which is how a duplicate could creep in unnoticed. Note it does not bite while
`section_id` is NULL: Postgres treats NULLs as DISTINCT in a unique index, so
all 21 existing rows pass regardless. It starts constraining when 138 lands,
which is another reason not to leave that window open.

Verified before writing: 21 subjects, all names distinct, 3 sections
(Early Years / Primary / Secondary), and every mark, enrolment and timetable row
resolves to exactly one section through its pupil's class — 0 unplaceable.
"""
import sqlalchemy as sa
from alembic import op

revision = "137_subject_section_scope"
down_revision = "136_attendance_unique_day"
branch_labels = None
depends_on = None

TABLE = "subjects"
UQ = "uq_subjects_org_section_name"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("section_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        f"fk_{TABLE}_section", TABLE, "school_sections",
        ["section_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_unique_constraint(UQ, TABLE, ["org_id", "section_id", "name"])
    op.create_index(f"ix_{TABLE}_org_section", TABLE, ["org_id", "section_id"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_org_section", table_name=TABLE)
    op.drop_constraint(UQ, TABLE, type_="unique")
    op.drop_constraint(f"fk_{TABLE}_section", TABLE, type_="foreignkey")
    op.drop_column(TABLE, "section_id")
