"""Add Fairview's real report-card columns, per section, for the current session.

From the Educare pages (max score in brackets):
  Secondary:  CA 1 (20)  CA 2 (20)  EXAM (60)            TOTAL (100)
  Junior:     CA 1 (20)  PRJ (10)   C.E (10)  EXAM (60)  TOTAL (100)

Each column is scoped to the year groups of the classes that are in that section
(read from school_classes.level, never typed in here), for every term, in the
Full-Term sub-term. Nursery prints no marks and is skipped.

THIS ONLY ADDS. It never edits or deletes an existing column, because existing
columns hold marks. The old unscoped columns (CBT / THEORY / PRJ / PBT / EXAM)
carry year_group NULL, which means "all levels", so they would still print beside
the new ones. The dry run lists them; retiring them is a separate decision that
moves or discards the marks entered against them.

Idempotent: a column that already exists for that (session, term, sub-term, year
group, name) is left alone.

DRY RUN BY DEFAULT.

    python -m scripts.configure_card_columns "<DSN>"
    python -m scripts.configure_card_columns "<DSN>" --write
"""
from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, AcademicTerm, Assessment, Cumulative,
    CumulativeComponent, SchoolSection,
)
from app.models.modules.school import SchoolClass
from app.services.report_sections import report_keys_for

SUB_TERM = "Full-Term"
SETS = {
    "secondary-report": [("CA 1", "CA1", 20), ("CA 2", "CA2", 20), ("EXAM", "EXAM", 60)],
    "junior-report": [("CA 1", "CA1", 20), ("PRJ", "PRJ", 10), ("C.E", "CE", 10), ("EXAM", "EXAM", 60)],
}


async def plan_and_apply(db: AsyncSession, org_id: str, write: bool) -> dict:
    out = {"added": [], "existing": 0, "problems": [], "unscoped_left": []}
    sess = (await db.execute(select(AcademicSession).where(
        AcademicSession.org_id == org_id, AcademicSession.is_current == True))).scalars().first()  # noqa: E712
    if not sess:
        out["problems"].append("no current academic session")
        return out
    sub = (await db.execute(select(AcademicSubTerm).where(
        AcademicSubTerm.org_id == org_id, AcademicSubTerm.name == SUB_TERM))).scalars().first()
    if not sub:
        out["problems"].append(f"no sub-term named {SUB_TERM!r}")
        return out
    terms = (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == org_id)
                              .order_by(AcademicTerm.position))).scalars().all()
    secs = (await db.execute(select(SchoolSection).where(SchoolSection.org_id == org_id))).scalars().all()
    keys = report_keys_for(secs)

    have_a = {(a.term_id, (a.year_group or "").upper(), a.name): a for a in (await db.execute(
        select(Assessment).where(Assessment.org_id == org_id, Assessment.session_id == sess.id,
                                 Assessment.sub_term_id == sub.id))).scalars().all()}
    have_c = {(c.term_id, (c.year_group or "").upper(), c.name): c for c in (await db.execute(
        select(Cumulative).where(Cumulative.org_id == org_id, Cumulative.session_id == sess.id,
                                 Cumulative.sub_term_id == sub.id))).scalars().all()}

    for report_key, cols in SETS.items():
        sec_id = next((i for i, k in keys.items() if k == report_key), None)
        if not sec_id:
            out["problems"].append(f"no section resolves to {report_key}")
            continue
        levels = sorted({(lv or "").strip().upper() for lv in (await db.execute(
            select(SchoolClass.level).where(SchoolClass.org_id == org_id,
                                            SchoolClass.section_id == sec_id))).scalars().all() if (lv or "").strip()})
        if not levels:
            out["problems"].append(f"{report_key}: its section has no classes with a level")
            continue
        for term in terms:
            for yg in levels:
                comps = []
                for pos, (name, code, mx) in enumerate(cols):
                    a = have_a.get((term.id, yg, name))
                    if a:
                        out["existing"] += 1
                    else:
                        out["added"].append(f"{report_key} {term.name} {yg}: {name} ({mx})")
                        if write:
                            a = Assessment(name=name, code=code, max_score=Decimal(mx), session_id=sess.id,
                                           term_id=term.id, sub_term_id=sub.id, year_group=yg,
                                           decimal_places=0, position=pos, org_id=org_id)
                            db.add(a)
                            await db.flush()
                            have_a[(term.id, yg, name)] = a
                    comps.append(a)
                if (term.id, yg, "TOTAL") in have_c:
                    out["existing"] += 1
                    continue
                out["added"].append(f"{report_key} {term.name} {yg}: TOTAL (100)")
                if write:
                    c = Cumulative(name="TOTAL", code="TOTAL", session_id=sess.id, term_id=term.id,
                                   sub_term_id=sub.id, year_group=yg, cumul_type="score",
                                   decimal_places=0, position=len(cols), org_id=org_id)
                    db.add(c)
                    await db.flush()
                    for pos, a in enumerate(comps):
                        db.add(CumulativeComponent(cumulative_id=c.id, ref_type="assessment",
                                                   ref_id=a.id, position=pos, org_id=org_id))
                    have_c[(term.id, yg, "TOTAL")] = c

    out["unscoped_left"] = sorted({a.name for a in (await db.execute(select(Assessment).where(
        Assessment.org_id == org_id, Assessment.session_id == sess.id,
        Assessment.year_group.is_(None)))).scalars().all()})
    if write:
        await db.flush()
    return out


async def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    dsn = (args[0] if args else os.environ.get("DATABASE_URL", "")).split("?")[0]
    if not dsn:
        sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")
    engine = create_async_engine(dsn)
    async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as db:
        org_id = (await db.execute(select(SchoolSection.org_id).limit(1))).scalar_one_or_none()
        if not org_id:
            sys.exit("No sections found.")
        r = await plan_and_apply(db, org_id, write)
        print("WRITE" if write else "DRY RUN")
        for p in r["problems"]:
            print("  !", p)
        for a in r["added"]:
            print("  +", a)
        print(f"  = {r['existing']} already present")
        if r["unscoped_left"]:
            print("  note: these old all-level columns still print beside the new ones:",
                  ", ".join(r["unscoped_left"]))
        if write:
            await db.commit()
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
