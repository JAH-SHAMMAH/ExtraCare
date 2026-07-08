"""Normalize term values to canonical Term 1/2/3 across the remaining tables

Revision ID: 040_normalize_term_extra
Revises: 039_cbt_phase_c
Create Date: 2026-07-08 16:00:00.000000

Migration 038 normalized only grades + exams. Several other tables carry the same
free-text ``term`` field, filled from UI inputs that were also free text, so they
accumulated the same "1st Term" vs "Term 1" drift. This applies the identical,
conservative mapping (only recognised old variants are rewritten; anything else —
e.g. "Semester 1", "Closing" — is left untouched) to the rest of the academic-term
tables so the whole app agrees on the canonical set the UI now enforces.

Excluded on purpose: student_fee_records.term uses a separate "term1_2024"/"annual"
code scheme for the fees flow — not the academic-term label — so it is not touched.

Data normalization is one-way — downgrade is a no-op (the original free text
isn't recoverable).
"""

from alembic import op
import sqlalchemy as sa


revision = "040_normalize_term_extra"
down_revision = "039_cbt_phase_c"
branch_labels = None
depends_on = None

# Same recognised-variant map as migration 038.
_MAP = {
    "Term 1": ["1st term", "first term", "term 1", "term1"],
    "Term 2": ["2nd term", "second term", "term 2", "term2"],
    "Term 3": ["3rd term", "third term", "term 3", "term3"],
}

# Academic-term tables NOT already handled by 038 (grades, exams).
_TABLES = (
    "mentor_reports",
    "academic_sessions",
    "subject_selections",
    "transcripts",
    "report_approvals",
    "recognitions",
    "teacher_ratings",
)


def upgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        for canonical, variants in _MAP.items():
            placeholders = ", ".join(f":v{i}" for i in range(len(variants)))
            params = {"canon": canonical, **{f"v{i}": v for i, v in enumerate(variants)}}
            conn.execute(
                sa.text(f"UPDATE {table} SET term = :canon WHERE lower(trim(term)) IN ({placeholders})"),
                params,
            )


def downgrade() -> None:
    # One-way data normalization — the original free-text values are not recoverable.
    pass
