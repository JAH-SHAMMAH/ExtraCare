"""Report Setup configuration Fairview confirmed: thresholds, Mock, Promotional.

Three independent pieces, all inserts — no schema change, no migration:

  1. report_branding thresholds. The table has NO ROW at all, so this creates one:
     full_term_passmark 40, mid_term_passmark 40, min_average_honours 80.
     40 is exactly the F/P boundary on the nine-band scale, so "pass" means what
     the scale says. 80 is the B band edge, so Honours starts at a band boundary
     rather than cutting C in half.

  2. A "Mock" sub-term. Educare shows Mock under Spring only, but AcademicSubTerm
     has no term link — it is org-wide — so "Spring-only" is not expressible as
     configuration. It is created once and simply has assessments only where the
     school puts them.

  3. "Promotional Exam Score", an assessment in Summer / Full-Term, in its own
     group so it does not aggregate with the CBT scores.

WHAT THIS DOES NOT FIX. Every subject currently grades as F on the report card,
because `report_card` reads a DISPLAY cumulative to get a percentage and
`cumulatives` is empty — with none, pct is hardcoded 0 and 0 falls in the F band.
Adding assessments does not change that. The card needs a cumulative structure,
which is the next step (Sessional Score), not this one.

DRY RUN BY DEFAULT.

    python -m scripts.configure_report_setup "<DSN>"
    python -m scripts.configure_report_setup "<DSN>" --write
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, AssessmentGroup, ReportBranding,
)

THRESHOLDS = {
    "full_term_passmark": Decimal("40"),
    "mid_term_passmark": Decimal("40"),
    "min_average_honours": Decimal("80"),
}
MOCK_SUB_TERM = "Mock"
PROMO = {
    "name": "Promotional Exam Score",
    "code": "PROMO",
    "max_score": Decimal("100"),
    "term": "Summer",
    "sub_term": "Full-Term",
    "group": "Promotional Exam",
    "year_group": None,      # all levels
    "decimal_places": 0,
}


def _dsn() -> str:
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            return a.split("?")[0]
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env.split("?")[0]
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def main() -> int:
    write = "--write" in sys.argv
    engine = create_async_engine(_dsn(), echo=False, connect_args={"ssl": "require"})
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        print(f"{'WRITE' if write else 'DRY RUN'}\n")
        planned = 0

        org_id = (await db.execute(select(AcademicTerm.org_id).limit(1))).scalar_one_or_none()
        if not org_id:
            sys.exit("No academic terms found — cannot resolve the organisation.")

        # ── 1. thresholds ─────────────────────────────────────────────────────
        br = (await db.execute(select(ReportBranding).where(ReportBranding.org_id == org_id))).scalars().first()
        if br:
            print("thresholds  = report_branding row exists; updating the three values:")
            for k, v in THRESHOLDS.items():
                print(f"              {k:<22} {getattr(br, k)} -> {v}")
                if write:
                    setattr(br, k, v)
            planned += 1
        else:
            print("thresholds  + creating the report_branding row (there is none):")
            for k, v in THRESHOLDS.items():
                print(f"              {k:<22} -> {v}")
            planned += 1
            if write:
                db.add(ReportBranding(id=str(uuid.uuid4()), org_id=org_id, **THRESHOLDS))

        # ── 2. Mock sub-term ──────────────────────────────────────────────────
        print()
        subs = {s.name: s for s in (await db.execute(
            select(AcademicSubTerm).where(AcademicSubTerm.org_id == org_id))).scalars().all()}
        if MOCK_SUB_TERM in subs:
            print(f"sub-term    = '{MOCK_SUB_TERM}' already exists")
        else:
            pos = max([s.position or 0 for s in subs.values()] or [0]) + 1
            print(f"sub-term    + '{MOCK_SUB_TERM}' (position {pos}); existing: {', '.join(sorted(subs)) or 'none'}")
            print(f"              org-wide, as all sub-terms are — it carries assessments only where created")
            planned += 1
            if write:
                db.add(AcademicSubTerm(id=str(uuid.uuid4()), name=MOCK_SUB_TERM,
                                       position=pos, org_id=org_id))

        # ── 3. Promotional Exam Score ─────────────────────────────────────────
        print()
        term = (await db.execute(select(AcademicTerm).where(
            AcademicTerm.org_id == org_id, AcademicTerm.name == PROMO["term"]))).scalars().first()
        sub = subs.get(PROMO["sub_term"])
        if not term or not sub:
            print(f"assessment  ! need term '{PROMO['term']}' and sub-term '{PROMO['sub_term']}' — "
                  f"term={'ok' if term else 'MISSING'} sub-term={'ok' if sub else 'MISSING'}")
        else:
            grp = (await db.execute(select(AssessmentGroup).where(
                AssessmentGroup.org_id == org_id, AssessmentGroup.name == PROMO["group"]))).scalars().first()
            existing = (await db.execute(select(Assessment).where(
                Assessment.org_id == org_id, Assessment.term_id == term.id,
                Assessment.sub_term_id == sub.id, Assessment.name == PROMO["name"]))).scalars().first()
            if not grp:
                print(f"group       + '{PROMO['group']}' (kept separate so it does not aggregate with CBT)")
                planned += 1
            else:
                print(f"group       = '{PROMO['group']}' already exists")
            if existing:
                print(f"assessment  = '{PROMO['name']}' already exists in {PROMO['term']}/{PROMO['sub_term']}")
            else:
                print(f"assessment  + '{PROMO['name']}' ({PROMO['code']}) max {PROMO['max_score']} "
                      f"in {PROMO['term']}/{PROMO['sub_term']}, all levels")
                planned += 1
            if write:
                if not grp:
                    grp = AssessmentGroup(id=str(uuid.uuid4()), name=PROMO["group"],
                                          position=1, org_id=org_id)
                    db.add(grp)
                    await db.flush()
                if not existing:
                    db.add(Assessment(
                        id=str(uuid.uuid4()), name=PROMO["name"], code=PROMO["code"],
                        max_score=PROMO["max_score"], term_id=term.id, sub_term_id=sub.id,
                        group_id=grp.id, year_group=PROMO["year_group"],
                        decimal_places=PROMO["decimal_places"], position=0, org_id=org_id,
                    ))

        # ── the thing this does NOT fix ───────────────────────────────────────
        from app.models.modules.platform import Cumulative
        cums = (await db.execute(select(Cumulative).where(Cumulative.org_id == org_id))).scalars().all()
        print()
        print(f"note        cumulatives configured: {len(cums)}")
        if not cums:
            print("            Every subject still grades F on the report card: report_card reads")
            print("            a DISPLAY cumulative for its percentage, and with none pct is 0,")
            print("            which is the F band. Assessments alone do not fix it — that is the")
            print("            next step, not this one.")

        if write:
            await db.commit()
            print(f"\n[OK] {planned} change(s) applied.")
        else:
            print(f"\nDRY RUN — nothing written. {planned} change(s) would be made.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
