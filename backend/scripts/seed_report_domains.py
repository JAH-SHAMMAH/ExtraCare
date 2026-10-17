"""Seed a section's rated report lines (behaviour/skills) from a spec. Idempotent.

Specs come from Fairview's own Educare reports, never from a generic list. Secondary,
Junior and Nursery specs are all read off the real pages. The Nursery goal list
comes from a very small screenshot and must be confirmed. Nothing here guesses.

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

# Everything below is read off Fairview's own Educare report pages (Oct 2026
# screenshots), in printed order. Nothing is generic.
_KEY_1_5_SECONDARY = ("Skills & behaviour 1-5 (Secondary)", [
    ("1", "Progress encouraged"), ("2", "Approaching standards"),
    ("3", "Acceptable standards"), ("4", "Meets expectations"),
    ("5", "Exceeds expectation")])
_KEY_1_5_JUNIOR = ("Affective & psychomotor 1-5 (Junior)", [
    ("5", "Excellent Degree of Observable Trait"), ("4", "Good Degree of Observable Trait"),
    ("3", "Fair But Acceptable Degree of Observable Trait"),
    ("2", "Poor Level of Observable Trait"), ("1", "No Observable Trait")])

SPECS = {
    # One block, "SKILLS AND BEHAVIOUR" (Club/Sports Choice is free text, not a rating).
    "secondary-report": {"groups": [{
        "scale": _KEY_1_5_SECONDARY, "domain_type": "affective",
        "items": ["Self regulation", "Leadership", "Teamwork", "Peer relationship",
                  "Time management", "Confidence", "Obedience", "Respect for authorities",
                  "Appearance", "Care for school property",
                  "Activeness in co-curricular activities", "Handling of tools"]}]},
    # Two blocks side by side, AFFECTIVE and PSYCHOMOTOR, one KEYS box.
    "junior-report": {"groups": [
        {"scale": _KEY_1_5_JUNIOR, "domain_type": "affective",
         "items": ["Punctuality", "Attendance", "Reliability", "Neatness", "Politeness",
                   "Honesty", "Self control", "Attentiveness", "Perseverance",
                   "Spirit of cooperation", "Sense of responsibility", "Initiative",
                   "Organizational ability", "Relationship with staff", "Relationship with pupils"]},
        {"scale": _KEY_1_5_JUNIOR, "domain_type": "psychomotor",
         "items": ["Handwriting", "Games", "Sports", "Drawing and painting", "Crafts",
                   "Musical skills", "Fluency", "Gymnastics"]}]},
    # Nursery has no marks: each Early Learning Goal gets a teacher-written
    # achievement sentence (stored as the rating's comment). 18 goals, 8 areas.
    # Read from a very small screenshot of the Nursery page -- CONFIRM before go-live.
    "nursery-report": {"areas": [
        ("Communication And Language", ["Listening, Attention and Understanding", "Speaking"]),
        ("Physical Development", ["Gross Motor Skills", "Fine Motor Skills"]),
        ("Personal, Social And Emotional Development", ["Self-Regulation", "Managing Self", "Building Relationships"]),
        ("Literacy", ["Comprehension", "Word Reading", "Writing"]),
        ("Mathematics", ["Number", "Numerical Patterns"]),
        ("Understanding The World", ["Past and Present", "People, Culture and Communities", "The Natural World"]),
        ("Expressive Art And Design", ["Creating with Materials", "Being Imaginative and Expressive"]),
        ("Practical Life Work", ["Care for Self"]),
    ]},
}


async def _ensure_scale(db, org_id, scale_spec, write):
    name, labels = scale_spec
    sc = (await db.execute(select(GradingScale).where(
        GradingScale.org_id == org_id, GradingScale.name == name))).scalars().first()
    created = sc is None
    if sc is None and write:
        sc = GradingScale(name=name, scale_type="descriptor", purpose="keys",
                          is_provisional=False, org_id=org_id)
        db.add(sc)
        await db.flush()
        for i, (lab, meaning) in enumerate(labels):
            db.add(GradingBand(scale_id=sc.id, grade=lab, remark=meaning, position=i, org_id=org_id))
    return sc, created


async def seed(db: AsyncSession, org_id: str, report_key: str, write: bool) -> dict:
    """Returns {'section', 'scales_created', 'added', 'existing'}; changes nothing unless write."""
    spec = SPECS.get(report_key)
    if not spec:
        raise SystemExit(f"No spec for {report_key!r}. Known: {', '.join(SPECS)}")
    secs = (await db.execute(select(SchoolSection).where(SchoolSection.org_id == org_id))).scalars().all()
    sec_id = next((i for i, k in report_keys_for(secs).items() if k == report_key), None)
    if not sec_id:
        raise SystemExit(f"No section resolves to {report_key!r}.")
    out = {"section": sec_id, "scales_created": 0, "added": [], "existing": []}
    rows = (await db.execute(select(AssessmentDomain).where(
        AssessmentDomain.org_id == org_id, AssessmentDomain.section_id == sec_id))).scalars().all()
    have = {(d.domain_type, d.name.casefold(), d.parent_domain_id): d for d in rows}

    async def add(dtype, name, pos, scale, parent=None):
        key = (dtype, name.casefold(), parent.id if parent else None)
        if key in have:
            out["existing"].append(name)
            return have[key]
        out["added"].append(name)
        if not write:
            return None
        d = AssessmentDomain(section_id=sec_id, domain_type=dtype, name=name, position=pos, org_id=org_id,
                             rating_scale_id=scale.id if scale else None,
                             parent_domain_id=parent.id if parent else None)
        db.add(d)
        await db.flush()
        have[key] = d
        return d

    for g in spec.get("groups", []):
        sc, created = await _ensure_scale(db, org_id, g["scale"], write)
        out["scales_created"] += int(created)
        for pos, item in enumerate(g["items"]):
            await add(g["domain_type"], item, pos, sc)
    pos = 0
    for ai, (area, goals) in enumerate(spec.get("areas", [])):
        parent = await add("eyfs_area", area, ai, None)
        for goal in goals:
            if parent is None:            # dry run, and the area is not in the database yet
                out["added"].append(goal)
            else:
                await add("eyfs_goal", goal, pos, None, parent)
            pos += 1
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
        print(f"  scales  {r['scales_created']} to create")
        print(f"  add     {len(r['added'])}: {', '.join(r['added']) or '-'}")
        print(f"  exists  {len(r['existing'])}")
        if write:
            await db.commit()
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
