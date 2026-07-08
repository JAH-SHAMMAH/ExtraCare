"""Normalize grade/exam term values to the canonical Term 1/2/3

Revision ID: 038_normalize_term_values
Revises: 037_add_cbt_question_bank
Create Date: 2026-07-08 14:00:00.000000

Term was free-text, so grades/exams accumulated "1st Term" vs "Term 1" etc.,
which broke the report-card term filter (the parent picked "1st Term" while the
exam wrote "Term 1"). This normalizes the recognised old formats to the canonical
set the UI now enforces. Only grades + exams are touched — fees use their own
term1/term2/term3 code scheme; unrecognised values (e.g. "Closing") are left as-is.

Data normalization is one-way — downgrade is a no-op (the original free text
isn't recoverable).
"""

from alembic import op
import sqlalchemy as sa


revision = "038_normalize_term_values"
down_revision = "037_add_cbt_question_bank"
branch_labels = None
depends_on = None

_MAP = {
    "Term 1": ["1st term", "first term", "term 1", "term1"],
    "Term 2": ["2nd term", "second term", "term 2", "term2"],
    "Term 3": ["3rd term", "third term", "term 3", "term3"],
}


def upgrade() -> None:
    conn = op.get_bind()
    for table in ("grades", "exams"):
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
