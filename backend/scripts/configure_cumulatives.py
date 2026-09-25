"""Step 3 data: the per-term TOTAL cumulative — the thing that ends the F grades.

WHY EVERY SUBJECT GRADES F. `report_card` gets its percentage from a DISPLAY
cumulative (`_pick_display_cumulative`). With `cumulatives` empty there is no
display, so the code takes its `(0, 0)` branch, pct is 0, and 0 lands in the F
band. The marks were never the problem: 1,799 scores are sitting in
student_assessment_scores spread right across 0-100. Nothing was reading them.

WHAT THIS CREATES. For each term that actually has assessments, one cumulative
named TOTAL of type `percentage` over that term's assessments. `percentage`
means value = Σscores / Σmaxes * 100, so a pupil's 74 out of 100 becomes 74%,
which is what the nine bands are expressed in. `_pick_display_cumulative`
prefers a cumulative named exactly "TOTAL", so naming it that is what makes it
the display column rather than an also-ran.

WHY NOT /cumulatives/bootstrap. That endpoint encodes Fairview's full Educare
structure — HALF TERM TOTAL, %, CA 1, TOTAL over CBT+Theory+PRJ+PBT+EXAM — and
matches assessments by NAME against "CBT", "THEORY", "PRJ", "PBT", "EXAM". Ours
is named "CBT Exam Score" (code CBT) and the other four do not exist, so it hits
`continue`, creates nothing, and returns 200 with an empty list. It is the right
target once the full assessment set exists; it cannot do anything today.

SPRING has no assessments, so it gets no cumulative and contributes nothing to
the Sessional Score — which is the honest outcome, not a bug: the Sessional
Score reports how many terms it counted.

DRY RUN BY DEFAULT.

    python -m scripts.configure_cumulatives "<DSN>"
    python -m scripts.configure_cumulatives "<DSN>" --write
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
    AcademicSubTerm, AcademicTerm, Assessment, Cumulative, CumulativeComponent,
    GradingBand, GradingScale, StudentAssessmentScore,
)

DISPLAY_NAME = "TOTAL"       # _pick_display_cumulative matches this exactly


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

        terms = (await db.execute(select(AcademicTerm).where(
            AcademicTerm.org_id == org_id).order_by(AcademicTerm.position, AcademicTerm.name))).scalars().all()
        subs = {s.id: s for s in (await db.execute(select(AcademicSubTerm).where(
            AcademicSubTerm.org_id == org_id))).scalars().all()}
        assessments = (await db.execute(select(Assessment).where(
            Assessment.org_id == org_id))).scalars().all()
        existing = (await db.execute(select(Cumulative).where(
            Cumulative.org_id == org_id))).scalars().all()

        for t in terms:
            t_asmts = [a for a in assessments if a.term_id == t.id]
            print(f"{t.name}")
            if not t_asmts:
                print(f"  .  no assessments — skipped (contributes nothing to the Sessional Score)")
                continue

            # One TOTAL per sub-term the term's assessments actually live in.
            by_sub: dict[str, list] = {}
            for a in t_asmts:
                by_sub.setdefault(a.sub_term_id, []).append(a)

            for sub_id, group in by_sub.items():
                sub_name = subs[sub_id].name if sub_id in subs else sub_id
                already = next((c for c in existing
                                if c.term_id == t.id and c.sub_term_id == sub_id
                                and (c.name or "").strip().upper() == DISPLAY_NAME), None)
                names = ", ".join(f"{a.name} (/{a.max_score:g})" for a in group)
                if already:
                    print(f"  =  {sub_name}: '{DISPLAY_NAME}' already exists")
                    continue
                print(f"  +  {sub_name}: '{DISPLAY_NAME}' (percentage) over {len(group)} assessment(s)")
                print(f"       {names}")
                planned += 1
                if write:
                    c = Cumulative(id=str(uuid.uuid4()), org_id=org_id, name=DISPLAY_NAME,
                                   term_id=t.id, sub_term_id=sub_id, cumul_type="percentage",
                                   decimal_places=2, position=0)
                    db.add(c)
                    await db.flush()
                    for i, a in enumerate(sorted(group, key=lambda x: (x.position or 0, x.name))):
                        db.add(CumulativeComponent(id=str(uuid.uuid4()), org_id=org_id,
                                                   cumulative_id=c.id, ref_type="assessment",
                                                   ref_id=a.id, position=i))
                    await db.flush()

        # ── what this will do to the grades, before it does it ────────────────
        print("\nprojected effect on the 1,799 marks")
        scale = (await db.execute(select(GradingScale).where(
            GradingScale.org_id == org_id, GradingScale.scale_type == "numeric",
            GradingScale.purpose == "grade").order_by(
            GradingScale.show_in_table.desc()))).scalars().first()
        bands = sorted((await db.execute(select(GradingBand).where(
            GradingBand.scale_id == scale.id, GradingBand.org_id == org_id))).scalars().all(),
            key=lambda b: float(b.min_score or 0), reverse=True) if scale else []
        scores = (await db.execute(select(StudentAssessmentScore.score).where(
            StudentAssessmentScore.org_id == org_id))).scalars().all()

        from app.services.grading import letter_for
        dist: dict[str, int] = {}
        for s in scores:
            if s is None:
                continue
            g = letter_for(float(s), 100, bands) or "(none)"
            dist[g] = dist.get(g, 0) + 1
        order = [b.grade for b in bands] + ["(none)"]
        total = sum(dist.values()) or 1
        print(f"  currently: every one of them renders F (pct pinned to 0)")
        print(f"  after:")
        for g in order:
            n = dist.get(g, 0)
            if n:
                print(f"     {g:<6} {n:>5}  {n*100//total:>3}%  {'#' * (n // 20)}")
        if dist.get("(none)"):
            print(f"  !  {dist['(none)']} mark(s) match no band — check the band edges")

        if write:
            await db.commit()
            print(f"\n[OK] {planned} cumulative(s) created.")
        else:
            print(f"\nDRY RUN — nothing written. {planned} cumulative(s) would be created.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
