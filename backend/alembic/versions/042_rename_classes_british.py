"""Rename classes to the British Year scheme (names + levels) + add Play Group / Pre-Nursery

Revision ID: 042_rename_classes_british
Revises: 041_academic_weeks
Create Date: 2026-07-08 18:30:00.000000

Renames the 14 Nigerian-scheme classes (Nursery 1–2 / Primary 1–6 / JSS 1–3 /
SS 1–3) to the British Year scheme AND remaps their ``level`` bucket to
Early Years / Primary / Secondary, so the level field can't leak the old naming
(e.g. a class named "Year 7" no longer carries level="Junior Secondary").

Names/levels only — every ``school_classes.id`` is preserved, so all student /
grade / timetable / exam / cbt_exam FKs (which reference the class id, never the
name) stay intact. Then adds Play Group + Pre-Nursery as new EMPTY classes per
org (they have no equivalent in the old data). Reversible: downgrade restores
both the old names and the old levels, and drops the 2 new classes only if empty.
"""
import uuid

from alembic import op
from sqlalchemy import text


revision = "042_rename_classes_british"
down_revision = "041_academic_weeks"
branch_labels = None
depends_on = None

# (old_name, new_name, old_level, new_level)
RENAMES = [
    ("Nursery 1", "Nursery",   "Nursery",          "Early Years"),
    ("Nursery 2", "Reception", "Nursery",          "Early Years"),
    ("Primary 1", "Year 1",    "Primary",          "Primary"),
    ("Primary 2", "Year 2",    "Primary",          "Primary"),
    ("Primary 3", "Year 3",    "Primary",          "Primary"),
    ("Primary 4", "Year 4",    "Primary",          "Primary"),
    ("Primary 5", "Year 5",    "Primary",          "Primary"),
    ("Primary 6", "Year 6",    "Primary",          "Primary"),
    ("JSS 1",     "Year 7",    "Junior Secondary", "Secondary"),
    ("JSS 2",     "Year 8",    "Junior Secondary", "Secondary"),
    ("JSS 3",     "Year 9",    "Junior Secondary", "Secondary"),
    ("SS 1",      "Year 10",   "Senior Secondary", "Secondary"),
    ("SS 2",      "Year 11",   "Senior Secondary", "Secondary"),
    ("SS 3",      "Year 12",   "Senior Secondary", "Secondary"),
]
# New early-years classes (no old equivalent).
NEW_CLASSES = [("Play Group", "Early Years"), ("Pre-Nursery", "Early Years")]


def upgrade() -> None:
    conn = op.get_bind()
    for old_name, new_name, _old_level, new_level in RENAMES:
        conn.execute(
            text("UPDATE school_classes SET name = :new, level = :level WHERE name = :old"),
            {"new": new_name, "level": new_level, "old": old_name},
        )
    # Add the two early-years classes for each org that already has classes.
    orgs = [r[0] for r in conn.execute(text("SELECT DISTINCT org_id FROM school_classes")).fetchall()]
    for org_id in orgs:
        ay = conn.execute(
            text("SELECT academic_year FROM school_classes WHERE org_id = :o AND academic_year IS NOT NULL LIMIT 1"),
            {"o": org_id},
        ).scalar()
        for name, level in NEW_CLASSES:
            exists = conn.execute(
                text("SELECT 1 FROM school_classes WHERE org_id = :o AND name = :n"),
                {"o": org_id, "n": name},
            ).scalar()
            if not exists:
                conn.execute(
                    text(
                        "INSERT INTO school_classes (id, name, level, academic_year, org_id, created_at, updated_at) "
                        "VALUES (:id, :n, :l, :ay, :o, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {"id": str(uuid.uuid4()), "n": name, "l": level, "ay": ay, "o": org_id},
                )


def downgrade() -> None:
    conn = op.get_bind()
    # Drop the two added classes — but only if still empty, never orphan students.
    for name, _ in NEW_CLASSES:
        for (cid,) in conn.execute(text("SELECT id FROM school_classes WHERE name = :n"), {"n": name}).fetchall():
            n = conn.execute(text("SELECT count(*) FROM students WHERE class_id = :c"), {"c": cid}).scalar()
            if n == 0:
                conn.execute(text("DELETE FROM school_classes WHERE id = :c"), {"c": cid})
    for old_name, new_name, old_level, _new_level in RENAMES:
        conn.execute(
            text("UPDATE school_classes SET name = :old, level = :level WHERE name = :new"),
            {"old": old_name, "level": old_level, "new": new_name},
        )
