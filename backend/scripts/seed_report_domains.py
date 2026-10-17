"""Seed a section's rated report lines (behaviour/skills) from a spec. Idempotent.

Specs come from Fairview's own Educare reports, never from a generic list. Only
the Secondary spec is filled in so far (read off the Secondary report page);
Junior and Nursery are added when their pages are confirmed. Nothing here guesses.

DRY RUN BY DEFAULT.

    python -m scripts.seed_report_domains "<DSN>" secondary-report
    python -m scripts.seed_report_domains "<DSN>" secondary-report --write
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import AssessmentDomain, GradingBand, GradingScale, SchoolSection
from app.services.report_sections import report_keys_for

# Educare "SKILLS AND BEHAVIOUR" block on the Secondary report, in printed order,
# with the printed KEYS (1-5). Club/Sports Choice is a separate free-text panel
# on the Educare page and is not a rating, so it is not seeded here.
SPECS = {
    "secondary-report": {
        "scale": ("Skills & behaviour 1-5 (Fairview)", [
            ("1", "Progress encouraged"), ("2", "Approaching standards"),
            ("3", "Acceptable standards"), ("4", "Meets expectations"),
            ("5", "Exceeds expectation")]),
        "domain_type": "affective",
        "items": ["Self regulation", "Leadership", "Teamwork", "Peer relationship",
                  "Time management", "Confidence", "Obedience", "Respect for authorities",
                  "Appearance", "Care for school property",
                  "Activeness in co-curricular activities", "Handling of tools"],
    },
}


async def seed(db: AsyncSession, org_id: str, report_key: str, write: bool) -> dict:
    """Returns {'section', 'scale_created', 'added', 'existing'}; changes nothing unless write."""
    spec = SPECS.get(report_key)
    if not spec:
        raise SystemExit(f"No spec for {report_key!r} yet. Known: {', '.join(SPECS)}")
    secs = (await db.execute(select(SchoolSection).where(SchoolSection.org_id == org_id))).scalars().all()
    sec_id = next((i for i, k in report_keys_for(secs).items() if k == report_key), None)
    if not sec_id:
        raise SystemExit(f"No section resolves to {report_key!r}.")
    name, labels = spec["scale"]
    scale = (await db.execute(select(GradingScale).where(
        GradingScale.org_id == org_id, GradingScale.name == name))).scalars().first()
    out = {"section": sec_id, "scale_created": scale is None, "added": [], "existing": []}
    if scale is None and write:
        scale = GradingScale(name=name, scale_type="descriptor", purpose="keys",
                             is_provisional=False, org_id=org_id)
        db.add(scale)
        await db.flush()
        for i, (lab, meaning) in enumerate(labels):
            db.add(GradingBand(scale_id=scale.id, grade=lab, remark=meaning, position=i, org_id=org_id))
    have = {d.name.casefold() for d in (await db.execute(select(AssessmentDomain).where(
        AssessmentDomain.org_id == org_id, AssessmentDomain.section_id == sec_id,
        AssessmentDomain.domain_type == spec["domain_type"]))).scalars().all()}
    for pos, item in enumerate(spec["items"]):
        if item.casefold() in have:
            out["existing"].append(item)
            continue
        out["added"].append(item)
        if write:
            db.add(AssessmentDomain(section_id=sec_id, domain_type=spec["domain_type"], name=item,
                                    rating_scale_id=scale.id if scale else None, position=pos, org_id=org_id))
    if write:
        await db.flush()
    return out


async def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    dsn = (args[0] if len(args) > 1 else os.environ.get("DATABASE_URL", "")).split("?")[0]
    key = args[-1] if args else ""
    if not dsn or len(args) < 1:
        sys.exit("Usage: seed_report_domains <DSN> <report-key> [--write]")
    engine = create_async_engine(dsn)
    async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as db:
        org_id = (await db.execute(select(SchoolSection.org_id).limit(1))).scalar_one_or_none()
        if not org_id:
            sys.exit("No sections found.")
        r = await seed(db, org_id, key, write)
        print(("WRITE" if write else "DRY RUN"), key)
        print(f"  scale   {'+ create' if r['scale_created'] else '= exists'}")
        print(f"  add     {len(r['added'])}: {', '.join(r['added']) or '-'}")
        print(f"  exists  {len(r['existing'])}")
        if write:
            await db.commit()
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
