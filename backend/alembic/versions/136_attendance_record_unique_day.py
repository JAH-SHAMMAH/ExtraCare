"""One attendance record per pupil per day

Revision ID: 136_attendance_unique_day
Revises: 135_student_report_term_id
Create Date: 2026-10-02

`attendance_records` is the daily roll-call — one present/absent/late/excused
status per pupil per day. It has carried only a PRIMARY KEY on `id`, so nothing
stopped the same pupil being marked twice on the same date, with two different
statuses. Nothing in the API deliberately does that, which is exactly why it
would go unnoticed: a double-submitted register, two teachers marking the same
class, or a retried request would quietly create a second row, and every count
built on this table — days present, the attendance denominator, the punctuality
figure on the report card — would be wrong by however many duplicates existed.

That matters more from here on, because the report card is about to DERIVE its
attendance figures from these rows rather than from a hand-typed number. A
duplicate would not look like an error; it would look like an extra school day.

VERIFIED AGAINST PRODUCTION before writing: 0 rows, and 0 (org, student, date)
groups holding more than one row, so the constraint applies without a dedupe
pass. The table being empty is also why this is cheap to do now and expensive to
do later.

(org_id, student_id, date) rather than (student_id, date): `student_id` already
implies an org, but every other uniqueness key in this schema leads with
`org_id` — `uq_student_assessment_score`, `uq_student_report_student_session_term`
— and a key that is shaped differently from its neighbours is one a later reader
has to stop and think about.
"""
from alembic import op

revision = "136_attendance_unique_day"
down_revision = "135_student_report_term_id"
branch_labels = None
depends_on = None

TABLE = "attendance_records"
UQ = "uq_attendance_record_student_day"


def upgrade() -> None:
    op.create_unique_constraint(UQ, TABLE, ["org_id", "student_id", "date"])


def downgrade() -> None:
    # Dropping it cannot fail on data — it only ever permitted more.
    op.drop_constraint(UQ, TABLE, type_="unique")
