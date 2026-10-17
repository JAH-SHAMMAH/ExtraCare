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
                try:                                    # runs every boot; add-only
                    if await ensure_letterheads(db, org_id):
                        await db.commit()
                except Exception:
                    await db.rollback()
                    log.exception("Letterhead setup failed for org %s", org_id)
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


# What each level's letterhead prints, as on the school's own report pages.
LETTERHEAD = {
    "secondary-report": "FAIRVIEW SECONDARY SCHOOL",
    "junior-report": "FAIRVIEW SCHOOL (PRE-SCHOOL and PRIMARY)",
    "nursery-report": "FAIRVIEW SCHOOL (PRE-SCHOOL and PRIMARY)",
}
MOTTO = {                      # pre-school and primary print the motto under the name
    "junior-report": ".... Soaring High",
    "nursery-report": ".... Soaring High",
}
ADDRESS = "PLOT 4674, EDWIN CLARK CRESCENT, GUZAPE, ABUJA"
EMAIL = "info@fairviewschool.com"


async def ensure_letterheads(db, org_id: str, write: bool = True) -> list[str]:
    """Give each report level its own letterhead (school name, address, email) when
    it has none. Add-only: a level that already has its own letterhead is untouched,
    and the school-wide default row is never edited. Idempotent."""
    from sqlalchemy import select
    from app.models.modules.platform import ReportBranding, SchoolSection
    from app.services.report_sections import report_keys_for

    secs = (await db.execute(select(SchoolSection).where(SchoolSection.org_id == org_id))).scalars().all()
    rows = (await db.execute(select(ReportBranding).where(ReportBranding.org_id == org_id))).scalars().all()
    default = next((r for r in rows if r.section_id is None), None)
    have = {r.section_id for r in rows if r.section_id}
    made = []
    for sec_id, key in report_keys_for(secs).items():
        if sec_id in have or key not in LETTERHEAD:
            continue
        made.append(key)
        if write:
            d = default
            db.add(ReportBranding(
                org_id=org_id, section_id=sec_id,
                school_name_alias=LETTERHEAD[key],
                # Only Secondary prints the address line; pre-school/primary do not.
                school_address=((d.school_address if d and d.school_address else ADDRESS) if key == "secondary-report" else None),
                school_email=((d.school_email if d and d.school_email else EMAIL) if key == "secondary-report" else None),
                school_website=d.school_website if d else None, school_phone=d.school_phone if d else None,
                school_motto=(MOTTO.get(key) or (d.school_motto if d else None)), logo_url=d.logo_url if d else None,
                head_signature_url=d.head_signature_url if d else None,
                school_head_title=(d.school_head_title if d and d.school_head_title else "Principal"),
                school_head_name=d.school_head_name if d else None,
                class_teacher_title=(d.class_teacher_title if d and d.class_teacher_title else "Class Teacher"),
                full_term_passmark=d.full_term_passmark if d else None,
                mid_term_passmark=d.mid_term_passmark if d else None,
                min_average_honours=d.min_average_honours if d else None,
            ))
    if write:
        await db.flush()
    return made
