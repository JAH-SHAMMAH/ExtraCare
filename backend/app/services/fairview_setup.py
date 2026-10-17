"""One preview/apply entry point for putting the Educare-style cards in place.

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
