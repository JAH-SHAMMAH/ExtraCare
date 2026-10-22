"""Secondary year labels: JSS1-3 / SSS1-3 become Year 7-12 (idempotent data rename)

Revision ID: 154_year_labels
Revises: 153_past_questions
"""
import sqlalchemy as sa
from alembic import op

revision = "154_year_labels"
down_revision = "153_past_questions"
branch_labels = None
depends_on = None

MAP = {"JSS1": "Year 7", "JSS2": "Year 8", "JSS3": "Year 9",
       "SSS1": "Year 10", "SSS2": "Year 11", "SSS3": "Year 12"}
# Tables that hold a level by name (report setup etc.).
NAME_MATCHED = ["assessments", "cumulatives", "report_level_settings",
                "report_subject_exclusions", "result_default_comments",
                "subject_groups", "period_groups"]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    def cols(t):
        return {c["name"] for c in insp.get_columns(t)}

    for old, new in MAP.items():
        # Year-group names are unique per org: skip a row whose target already exists.
        if "year_groups" in tables:
            bind.execute(sa.text(
                "UPDATE year_groups SET name = :new WHERE upper(name) = :old AND NOT EXISTS ("
                " SELECT 1 FROM year_groups y2 WHERE y2.org_id = year_groups.org_id AND y2.name = :new)"
            ), {"old": old, "new": new})
        if "school_classes" in tables:
            c = cols("school_classes")
            if "level" in c:
                bind.execute(sa.text("UPDATE school_classes SET level = :new WHERE upper(level) = :old"),
                             {"old": old, "new": new})
            # 'SSS1 A' -> 'Year 10 A'; a bare 'SSS1' too
            bind.execute(sa.text(
                "UPDATE school_classes SET name = :new || substr(name, :n) "
                "WHERE upper(name) = :old OR upper(substr(name, 1, :n1)) = :oldsp"
            ), {"new": new, "n": len(old) + 1, "old": old, "n1": len(old) + 1, "oldsp": old + " "})
        for t in NAME_MATCHED:
            if t in tables and "year_group" in cols(t):
                # Skip where a unique (org, year_group[, subject]) row for the new name already exists.
                try:
                    with bind.begin_nested():
                        bind.execute(sa.text(f"UPDATE {t} SET year_group = :new WHERE upper(year_group) = :old"),
                                     {"old": old, "new": new})
                except Exception:  # noqa: BLE001 — unique clash: leave that table's rows alone
                    pass


def downgrade() -> None:
    pass  # a label change; intentionally not reversed
