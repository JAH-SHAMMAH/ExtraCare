#!/usr/bin/env python
"""Configure a term's Full-Term marking scheme: CA(40) + Exam(60) summing to TOTAL.

Autumn is deliberately NOT a target. Its TOTAL is the CBT Exam Score alone and its
cards are published; re-weighting it would move 1,645 of 1,799 letters, because an
unmarked component is scored as zero by the evaluator. Weights apply from Spring
onward, to terms that have not been marked yet.

WHAT IT CREATES, all for (term, Full-Term):

    assessment  Continuous Assessment   max  40
    assessment  CBT Exam Score          max 100
    cumulative  CA    custom_percentage cap 40   <- Continuous Assessment
    cumulative  Exam  custom_percentage cap 60   <- CBT Exam Score
    cumulative  TOTAL percentage               <- CA + Exam

Assessments carry term_id, so each term needs its OWN rows; nothing is shared with
another term except the assessment GROUPS, which carry no term and are reused.

Idempotent: anything already present is left alone and reported. Dry run unless
--write is passed.

    python scripts/configure_term_weights.py <DSN> --term Spring
    python scripts/configure_term_weights.py <DSN> --term Spring --write
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

CA_NAME, EXAM_NAME = "Continuous Assessment", "CBT Exam Score"
CA_CAP, EXAM_CAP = 40, 60
SUB_TERM = ("Full-Term", "Full Term")
REFUSED = {"autumn"}          # published; see the module docstring


def _arg(flag: str, default: str | None = None) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _resolve(argv) -> str:
    skip = {"--term"}
    skip_next = False
    for a in argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if a in skip:
            skip_next = True
            continue
        if not a.startswith("--"):
            return a.split("?")[0]
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env.split("?")[0]
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def main() -> int:
    write = "--write" in sys.argv
    term_name = _arg("--term")
    if not term_name:
        sys.exit("--term is required, e.g. --term Spring")
    if term_name.strip().lower() in REFUSED:
        sys.exit(f"Refusing to re-weight {term_name}: its cards are published, and an "
                 f"unmarked component is scored as zero — this would rewrite every "
                 f"letter already sent to a parent.")

    url = _resolve(sys.argv)
    engine = create_async_engine(url, echo=False, connect_args={"ssl": "require"})
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from app.models.modules.platform import (
        AcademicSubTerm, AcademicTerm, Assessment, AssessmentGroup, Cumulative,
        CumulativeComponent, StudentAssessmentScore,
    )

    async with Session() as db:
        term = (await db.execute(select(AcademicTerm).where(
            AcademicTerm.name == term_name))).scalars().first()
        if not term:
            sys.exit(f"No term named {term_name!r}.")
        org = term.org_id
        sub = (await db.execute(select(AcademicSubTerm).where(
            AcademicSubTerm.org_id == org,
            AcademicSubTerm.name.in_(SUB_TERM)))).scalars().first()
        if not sub:
            sys.exit("No Full-Term sub-term is defined.")
        print(f"term {term.name} ({term.id}) / sub-term {sub.name} ({sub.id})")

        marked = (await db.execute(
            select(StudentAssessmentScore.id)
            .join(Assessment, Assessment.id == StudentAssessmentScore.assessment_id)
            .where(Assessment.term_id == term.id).limit(1))).scalars().first()
        if marked:
            print("\nWARNING: this term already has marks. Changing its weighting now")
            print("would re-grade them, exactly as it would have for Autumn.")
            if not write:
                print("Refusing in dry run; re-run deliberately if that is intended.")
            else:
                sys.exit("Refusing to re-weight a term that already carries marks.")

        planned: list[str] = []

        async def group(name: str, position: int) -> AssessmentGroup:
            g = (await db.execute(select(AssessmentGroup).where(
                AssessmentGroup.org_id == org, AssessmentGroup.name == name))).scalars().first()
            if g:
                print(f"  = assessment_group {name!r} exists")
                return g
            planned.append(f"assessment_group {name!r}")
            g = AssessmentGroup(id=str(uuid.uuid4()), name=name, position=position, org_id=org)
            if write:
                db.add(g)
                await db.flush()
            return g

        async def assessment(name: str, code: str, mx: int, grp, position: int) -> Assessment:
            a = (await db.execute(select(Assessment).where(
                Assessment.org_id == org, Assessment.term_id == term.id,
                Assessment.sub_term_id == sub.id, Assessment.name == name))).scalars().first()
            if a:
                print(f"  = assessment {name!r} exists (max {a.max_score})")
                return a
            planned.append(f"assessment {name!r} max {mx}")
            a = Assessment(id=str(uuid.uuid4()), name=name, code=code, max_score=mx,
                           term_id=term.id, sub_term_id=sub.id, decimal_places=0,
                           group_id=getattr(grp, "id", None), position=position, org_id=org)
            if write:
                db.add(a)
                await db.flush()
            return a

        async def cumulative(name: str, ctype: str, cap, position: int) -> Cumulative:
            c = (await db.execute(select(Cumulative).where(
                Cumulative.org_id == org, Cumulative.term_id == term.id,
                Cumulative.sub_term_id == sub.id, Cumulative.name == name))).scalars().first()
            if c:
                print(f"  = cumulative {name!r} exists ({c.cumul_type} cap {c.max_percent})")
                return c
            planned.append(f"cumulative {name!r} {ctype} cap {cap}")
            c = Cumulative(id=str(uuid.uuid4()), name=name, cumul_type=ctype,
                           max_percent=cap, term_id=term.id, sub_term_id=sub.id,
                           decimal_places=2, position=position, org_id=org)
            if write:
                db.add(c)
                await db.flush()
            return c

        async def component(cum, ref_type: str, ref, position: int) -> None:
            if getattr(cum, "id", None) and getattr(ref, "id", None):
                got = (await db.execute(select(CumulativeComponent).where(
                    CumulativeComponent.cumulative_id == cum.id,
                    CumulativeComponent.ref_id == ref.id))).scalars().first()
                if got:
                    print(f"  = component {cum.name} <- {getattr(ref, 'name', ref_type)} exists")
                    return
            planned.append(f"component {cum.name} <- {getattr(ref, 'name', ref_type)}")
            if write:
                db.add(CumulativeComponent(
                    id=str(uuid.uuid4()), cumulative_id=cum.id, ref_type=ref_type,
                    ref_id=ref.id, position=position, org_id=org))
                await db.flush()

        print("\n== rows ==")
        ca_group = await group(CA_NAME, 2)
        cbt_group = await group("CBT Exam Scores", 0)
        ca_a = await assessment(CA_NAME, "CA", CA_CAP, ca_group, 0)
        ex_a = await assessment(EXAM_NAME, "CBT", 100, cbt_group, 1)
        ca_c = await cumulative("CA", "custom_percentage", CA_CAP, 0)
        ex_c = await cumulative("Exam", "custom_percentage", EXAM_CAP, 1)
        total = await cumulative("TOTAL", "percentage", None, 2)
        await component(ca_c, "assessment", ca_a, 0)
        await component(ex_c, "assessment", ex_a, 0)
        await component(total, "cumulative", ca_c, 0)
        await component(total, "cumulative", ex_c, 1)

        print(f"\n{len(planned)} row(s) {'written' if write else 'would be created'}:")
        for p in planned:
            print(f"   + {p}")
        if write:
            await db.commit()
            print("\ncommitted")
        else:
            print("\n(dry run — nothing written. Pass --write.)")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
