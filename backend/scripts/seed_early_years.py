"""Seed Early Years: the EYFS domains, their descriptor scale, and the template.

WHAT THIS DELIBERATELY DOES NOT CALL: POST /report-config/bootstrap. That endpoint
would also create a SECOND numeric grading scale — "Grading Scale (A–F)" with the
stale 5-band 70/60/50/45/40 — and `purpose` defaults to 'grade' with
`show_in_table` True. Fairview already has exactly one grade scale, the nine-band
`Nigerian Secondary (A*-F)` verified against all 1,799 marks. Both scale pickers
select numeric + purpose='grade' ordered by show_in_table DESC and then take
.first(), so two rows tied on show_in_table resolve ARBITRARILY: every letter on
every report card could silently flip to the 5-band scale. It would also stamp
carries_cambridge on 10 subjects x 2 sections. None of that is wanted here.

So this seeds only what Early Years needs:

  1. `seed_domains` for the Early Years section. Section-scoped and, for
     curriculum='eyfs', it creates ONLY the descriptor scale
     (Emerging / Expected / Exceeding, non-provisional — a real published
     framework) plus the 7 EYFS Areas of Learning and their 17 Early Learning
     Goals. Descriptor scales are invisible to the numeric grade picker, so there
     is no collision.

  2. The Early Years ReportTemplate, with the values report-config/bootstrap would
     have given it: descriptive mode, no CA/exam weights, no grading scale, and
     the numeric table and class position suppressed — so an EYFS card renders as
     ratings rather than as marks.

Both steps are idempotent: `seed_domains` never duplicates a name, and the
template insert is skipped when the section already has one.

DRY RUN BY DEFAULT. The dry run really executes both steps into the session and
then ROLLS BACK, so what it reports is what the write would do, not a prediction
of it.

    python -m scripts.seed_early_years "<DSN>"
    python -m scripts.seed_early_years "<DSN>" --write
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import (
    AssessmentDomain, GradingBand, GradingScale, ReportTemplate, SchoolSection,
)

SECTION = "Early Years"

# Exactly what report-config/bootstrap gives the Early Years template, without the
# rest of what that endpoint does.
TEMPLATE = dict(
    name="Early Years (EYFS)",
    assessment_mode="descriptive",
    ca_weight=None,
    exam_weight=None,
    grading_scale_id=None,
    show_cognitive_table=False,   # a descriptive report has no marks table
    show_position=False,          # and does not rank four-year-olds
    show_attendance=True,
    show_affective=True,
    show_psychomotor=True,
    is_provisional=False,
)


class _Actor:
    """`seed_domains` only reads `current_user.org_id`, so this is all it needs —
    no real person is borrowed to attribute a seed to."""

    def __init__(self, org_id: str):
        self.org_id = org_id


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
        print(f"{'WRITE' if write else 'DRY RUN (executes, then rolls back)'}\n")

        sec = (await db.execute(select(SchoolSection).where(
            SchoolSection.name == SECTION))).scalars().first()
        if not sec:
            sys.exit(f"Section {SECTION!r} not found.")
        print(f"section   {sec.name}  curriculum={sec.curriculum!r}")
        if (sec.curriculum or "").lower() != "eyfs":
            sys.exit(f"  ! curriculum is {sec.curriculum!r}, not 'eyfs' — seed_domains "
                     f"would lay down psychomotor/affective domains instead of EYFS. "
                     f"Fix the section's curriculum first.")

        before_scales = {s.name for s in (await db.execute(select(GradingScale).where(
            GradingScale.org_id == sec.org_id))).scalars().all()}
        before_domains = (await db.execute(select(AssessmentDomain).where(
            AssessmentDomain.org_id == sec.org_id))).scalars().all()
        print(f"          existing scales: {sorted(before_scales) or 'none'}")
        print(f"          existing domains: {len(before_domains)}")

        # ── 1. domains + descriptor scale ─────────────────────────────────────
        print("\nstep 1   seed_domains (the real endpoint function)")
        from app.routers.modules.platform import seed_domains

        out = await seed_domains(section_id=sec.id, db=db, current_user=_Actor(sec.org_id))
        areas = [d for d in out if d.domain_type == "eyfs_area"]
        goals = [d for d in out if d.domain_type == "eyfs_goal"]
        other = [d for d in out if d.domain_type not in ("eyfs_area", "eyfs_goal")]
        print(f"          -> {len(areas)} area(s), {len(goals)} goal(s)"
              + (f", {len(other)} OTHER (unexpected)" if other else ""))
        for a in sorted(areas, key=lambda d: d.position):
            kids = [g.name for g in goals if g.parent_domain_id == a.id]
            print(f"             {a.name}")
            for k in kids:
                print(f"                - {k}")

        after_scales = {s.name: s for s in (await db.execute(select(GradingScale).where(
            GradingScale.org_id == sec.org_id))).scalars().all()}
        new_scales = set(after_scales) - before_scales
        print(f"\n          scales created: {sorted(new_scales) or 'none'}")
        for name in sorted(new_scales):
            s = after_scales[name]
            bands = (await db.execute(select(GradingBand).where(
                GradingBand.scale_id == s.id).order_by(GradingBand.position))).scalars().all()
            print(f"             {name}: type={s.scale_type} purpose={s.purpose!r} "
                  f"provisional={s.is_provisional}")
            print(f"             labels: {[b.grade for b in bands]}")
            if s.scale_type == "numeric":
                print(f"             !! NUMERIC scale created — this would compete with "
                      f"the existing grade scale. STOP.")

        # ── 2. the template ──────────────────────────────────────────────────
        print("\nstep 2   Early Years report template")
        existing_t = (await db.execute(select(ReportTemplate).where(
            ReportTemplate.org_id == sec.org_id,
            ReportTemplate.section_id == sec.id))).scalars().first()
        if existing_t:
            print(f"          = already exists: {existing_t.name!r} "
                  f"mode={existing_t.assessment_mode!r}")
        else:
            print(f"          + {TEMPLATE['name']!r}")
            for k, v in TEMPLATE.items():
                if k != "name":
                    print(f"             {k:<22} {v}")
            db.add(ReportTemplate(section_id=sec.id, org_id=sec.org_id, **TEMPLATE))
            await db.flush()

        # ── what did NOT change ──────────────────────────────────────────────
        print("\nguard    the numeric grade scale must be untouched")
        for r in (await db.execute(select(GradingScale).where(
                GradingScale.org_id == sec.org_id,
                GradingScale.scale_type == "numeric"))).scalars().all():
            n = len((await db.execute(select(GradingBand).where(
                GradingBand.scale_id == r.id))).scalars().all())
            print(f"          {r.name!r} purpose={r.purpose!r} "
                  f"show_in_table={r.show_in_table} bands={n}")
        numeric = (await db.execute(select(GradingScale).where(
            GradingScale.org_id == sec.org_id, GradingScale.scale_type == "numeric",
            GradingScale.purpose == "grade"))).scalars().all()
        if len(numeric) > 1:
            print(f"          !! {len(numeric)} numeric grade scales — the card's picker "
                  f"would resolve arbitrarily. NOT SAFE.")
            if write:
                await db.rollback()
                return 1
        else:
            print(f"          OK — exactly {len(numeric)} numeric grade scale")

        if write:
            await db.commit()
            print("\n[OK] committed.")
        else:
            await db.rollback()
            print("\nDRY RUN — rolled back, nothing written.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
