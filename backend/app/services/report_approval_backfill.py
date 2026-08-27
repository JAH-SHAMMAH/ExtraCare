"""Planner for the ReportApproval publish backfill (migration 125).

ONE set of queries, shared by the Alembic migration that writes the rows and the
dry-run script that previews them, so the preview is provably the thing that
runs rather than a hand-copied approximation of it.

Everything here takes a plain (sync) SQLAlchemy Connection — what Alembic hands
a migration, and what an async connection exposes through ``run_sync``.

Why this backfill exists: the parent report card gains a second gate on
``ReportApproval.stage == 'published'``. Grades already released to parents have
no workflow row behind them (the workflow was optional until now), so without a
backfill every currently-visible card would go blank the moment the gate ships.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text

# `grades.status` is a SQLAlchemy Enum(GradeStatus), which persists the member
# NAME — rows read 'PUBLISHED', not 'published'. Confirmed against production;
# matching on the lowercase value would silently select nothing and backfill
# nothing, which is the one failure mode this migration must not have.
PUBLISHED_STATUS = "PUBLISHED"

BACKFILL_NOTE = "Backfilled by migration 125 from grades already published to parents."


def _current_year_by_org(conn) -> dict[str, str]:
    """org_id -> current session name. Truthiness is evaluated in Python because
    `is_current` is a real bool on Postgres and 0/1 on SQLite."""
    rows = conn.execute(text("SELECT org_id, name, is_current FROM academic_sessions")).fetchall()
    return {r[0]: r[1] for r in rows if r[2]}


def _class_names(conn) -> dict[str, str]:
    rows = conn.execute(text("SELECT id, name FROM school_classes")).fetchall()
    return {r[0]: r[1] for r in rows}


def plan_backfill(conn) -> tuple[list[dict], list[dict]]:
    """Work out what the backfill would write, without writing it.

    Returns ``(to_create, skipped)``:

      to_create — one row per (org, class, term) that has published grades and no
                  report_approvals row yet.
      skipped   — pairs that already hold a row, with the stage it sits at, so a
                  re-run is a visible no-op and an operator can see what was left
                  alone (a pair parked at 'draft' would still hide its cards).

    Deliberately org-agnostic: any tenant with published grades is covered.
    Soft-deleted students are NOT excluded — their grades were published to a
    real parent at some point, and a class is in scope if any published grade
    points at it.
    """
    now = datetime.now(timezone.utc)
    years = _current_year_by_org(conn)
    names = _class_names(conn)

    pairs = conn.execute(
        text(
            """
            SELECT g.org_id, s.class_id, g.term,
                   COUNT(*) AS grade_rows,
                   COUNT(DISTINCT g.student_id) AS students
            FROM grades g
            JOIN students s ON s.id = g.student_id
            WHERE g.status = :status
              AND s.class_id IS NOT NULL
              AND g.term IS NOT NULL
            GROUP BY g.org_id, s.class_id, g.term
            ORDER BY g.org_id, s.class_id, g.term
            """
        ),
        {"status": PUBLISHED_STATUS},
    ).fetchall()

    existing = {
        (r[0], r[1], r[2]): r[3]
        for r in conn.execute(
            text("SELECT org_id, class_id, term, stage FROM report_approvals")
        ).fetchall()
    }

    to_create: list[dict] = []
    skipped: list[dict] = []
    for org_id, class_id, term, grade_rows, students in pairs:
        key = (org_id, class_id, term)
        display = {
            "org_id": org_id, "class_id": class_id, "class_name": names.get(class_id),
            "term": term, "grade_rows": grade_rows, "students": students,
        }
        if key in existing:
            skipped.append({**display, "existing_stage": existing[key]})
            continue
        to_create.append({
            **display,
            "id": str(uuid.uuid4()),
            "academic_year": years.get(org_id),
            "stage": "published",
            "notes": BACKFILL_NOTE,
            "published_at": now,
            "created_at": now,
            "updated_at": now,
        })
    return to_create, skipped


# Columns actually written — display-only keys from the plan (class_name,
# grade_rows, students) are not table columns and must not reach the INSERT.
_INSERT_COLUMNS = (
    "id", "org_id", "class_id", "academic_year", "term", "stage", "notes",
    "published_at", "created_at", "updated_at",
)


def apply_backfill(conn, to_create: list[dict]) -> int:
    """Insert the planned rows. Returns the count written."""
    if not to_create:
        return 0
    conn.execute(
        text(
            "INSERT INTO report_approvals "
            "(id, org_id, class_id, academic_year, term, stage, notes, published_at, created_at, updated_at) "
            "VALUES (:id, :org_id, :class_id, :academic_year, :term, :stage, :notes, "
            ":published_at, :created_at, :updated_at)"
        ),
        [{c: row[c] for c in _INSERT_COLUMNS} for row in to_create],
    )
    return len(to_create)
