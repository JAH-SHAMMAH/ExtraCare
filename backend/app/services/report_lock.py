"""Is a class's report frozen? One answer, shared by every write that could move
a published number.

`ReportApproval.stage == "published"` means the school released that class's term
to parents. Anything that edits the marks behind a released report changes what a
parent already read, with no trace and no re-approval — so the writes have to ask
first.

`ReportApproval.term` is the term NAME ("Term 1"), which is what the old
Grade-based pipeline stored and what migration 125 backfilled. The newer report
system keys on `AcademicTerm.id`, so callers holding an id resolve it through
`AcademicTerm.name` — verified to be the same vocabulary in production
('Term 1' / 'Term 2' / 'Term 3').
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modules.academics import ReportApproval
from app.models.modules.platform import AcademicTerm
from app.schemas.academics import REPORT_RELEASED_STAGE


async def published_terms_for_classes(
    db: AsyncSession, org_id: str, class_ids: set[str] | list[str],
) -> set[tuple[str, str]]:
    """The (class_id, term_name) pairs among `class_ids` whose report is published."""
    ids = {c for c in (class_ids or []) if c}
    if not ids:
        return set()
    rows = (await db.execute(
        select(ReportApproval.class_id, ReportApproval.term).where(
            ReportApproval.org_id == org_id,
            ReportApproval.class_id.in_(ids),
            ReportApproval.stage == REPORT_RELEASED_STAGE,
            ReportApproval.term.isnot(None),
        )
    )).all()
    return {(r[0], r[1]) for r in rows}


async def term_names_for_ids(
    db: AsyncSession, org_id: str, term_ids: set[str] | list[str],
) -> dict[str, str]:
    """AcademicTerm.id -> name, for callers that hold ids (the newer report system)."""
    ids = {t for t in (term_ids or []) if t}
    if not ids:
        return {}
    rows = (await db.execute(
        select(AcademicTerm.id, AcademicTerm.name).where(
            AcademicTerm.org_id == org_id, AcademicTerm.id.in_(ids)
        )
    )).all()
    return {r[0]: r[1] for r in rows}


async def find_published_block(
    db: AsyncSession, org_id: str, class_ids: set[str] | list[str],
    term_names: set[str] | list[str],
) -> tuple[str, str] | None:
    """The first (class_id, term_name) that is published, or None if none are.

    Returns rather than raises so each caller can react in the way that suits it:
    the report-entry endpoint refuses the write outright, while the CBT sync skips
    with a reason instead of failing a publish that is otherwise legitimate.
    """
    wanted = {t for t in (term_names or []) if t}
    if not wanted:
        return None
    for class_id, term in await published_terms_for_classes(db, org_id, class_ids):
        if term in wanted:
            return (class_id, term)
    return None


def locked_message(term: str, class_name: str | None = None) -> str:
    subject = f"{class_name}'s" if class_name else "This class's"
    return (
        f"{subject} {term} report is published — scores are frozen. Retract it to "
        f"'approved' or earlier in Report Workflow before editing, then publish again."
    )
