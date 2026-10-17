"""One preview/apply entry point for putting the Fairview-style cards in place.

Order matters: domains (skills / nursery goals) -> card columns -> carry old marks
onto them. Preview (write=False) changes nothing; apply runs in the caller's
transaction so a failure part-way leaves the database untouched.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.legacy_marks import align_legacy_marks


async def run_setup(db: AsyncSession, org_id: str, write: bool, align: bool = True) -> dict:
    from scripts.configure_card_columns import plan_and_apply
    from scripts.seed_report_domains import SPECS, seed

    domains = {}
    for key in SPECS:
        try:
            domains[key] = await seed(db, org_id, key, write)
        except SystemExit as e:           # section for that template does not exist
            domains[key] = {"skipped": str(e)}
    if write:
        await db.flush()
    columns = await plan_and_apply(db, org_id, write)
    if write:
        await db.flush()
    marks = await align_legacy_marks(db, org_id, write) if align else None
    return {"applied": write, "domains": domains, "columns": columns, "marks": marks}


async def auto_setup_on_boot(session_factory) -> None:
    """Runs once per school at startup so the new report cards simply appear.

    "Already done" = the school has a real CA 1 / EXAM column scoped to a level. After
    that nothing here runs again, so a column an admin later edits or removes is
    never re-added and marks are never re-split. Failures are logged and rolled
    back, never allowed to stop the app from starting.
    """
    import logging
    from sqlalchemy import select
    from app.models.modules.platform import Assessment, SchoolSection

    log = logging.getLogger(__name__)
    try:
        async with session_factory() as db:
            orgs = (await db.execute(select(SchoolSection.org_id).distinct())).scalars().all()
            for org_id in orgs:
                done = (await db.execute(select(Assessment.id).where(
                    Assessment.org_id == org_id, Assessment.name.in_(["CA 1", "EXAM"]),
                    Assessment.year_group.is_not(None), Assessment.year_group != "LEGACY").limit(1))).first()
                if done:
                    continue
                try:
                    res = await run_setup(db, org_id, write=True)
                    await db.commit()
                    log.info("Report card setup applied for org %s: %s", org_id, res.get("marks"))
                except Exception:
                    await db.rollback()
                    log.exception("Report card setup failed for org %s; left unchanged", org_id)
    except Exception:
        log.exception("Report card setup skipped")
