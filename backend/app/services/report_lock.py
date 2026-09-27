"""Is a class's report frozen? One answer, shared by every write that could move
a published number.

`ReportApproval.stage == "published"` means the school released that class's term
to parents. Anything that edits the marks behind a released report changes what a
parent already read, with no trace and no re-approval — so the writes have to ask
first.

`ReportApproval.term_id` is an AcademicTerm id (migration 131). It was the term
NAME, and that name is what caused the 2026-09-27 outage: the approvals said
'Term 1' while the school's only selectable terms were Autumn/Spring/Summer, so
this lock and the parent report-card gate — both matching BY NAME — found nothing
and reported every class as unreleased.

The previous version of this note claimed the vocabulary was "verified to be the
same in production ('Term 1' / 'Term 2' / 'Term 3')". It was not: production's
terms are Autumn/Spring/Summer. A stale "verified" claim in the file that guards
published marks is worse than no claim, so it is recorded here rather than
quietly deleted.

The LEGACY Grade store still keys on a term NAME and is deliberately staying that
way (it is being retired), so the boundary between this lock and `grades` needs an
id -> name resolution. That is the only place a name is still used here.
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
    """The (class_id, term_id) pairs among `class_ids` whose report is published.

    Returns IDS since migration 131. Callers that need a name for display resolve it
    through `term_names_for_ids`; callers comparing against the legacy Grade store
    (which is still name-keyed) do the same.
    """
    ids = {c for c in (class_ids or []) if c}
    if not ids:
        return set()
    rows = (await db.execute(
        select(ReportApproval.class_id, ReportApproval.term_id).where(
            ReportApproval.org_id == org_id,
            ReportApproval.class_id.in_(ids),
            ReportApproval.stage == REPORT_RELEASED_STAGE,
            ReportApproval.term_id.isnot(None),
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
    term_ids: set[str] | list[str],
) -> tuple[str, str] | None:
    """The first (class_id, term_id) that is published, or None if none are.

    Compares IDS since migration 131. Before that this took term NAMES, and a caller
    holding an id had to convert — which is exactly where a drifted name silently
    matched nothing and the lock reported every class as unreleased.

    Returns rather than raises so each caller can react in the way that suits it:
    the report-entry endpoint refuses the write outright, while the CBT sync skips
    with a reason instead of failing a publish that is otherwise legitimate.
    """
    wanted = {t for t in (term_ids or []) if t}
    if not wanted:
        return None
    for class_id, term_id in await published_terms_for_classes(db, org_id, class_ids):
        if term_id in wanted:
            return (class_id, term_id)
    return None


def locked_message(term: str, class_name: str | None = None) -> str:
    subject = f"{class_name}'s" if class_name else "This class's"
    return (
        f"{subject} {term} report is published — scores are frozen. Retract it to "
        f"'approved' or earlier in Report Workflow before editing, then publish again."
    )
