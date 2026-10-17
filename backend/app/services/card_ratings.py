"""Rated blocks (behaviour, skills, Early Learning Goals) for a report card.

Read-only. A line with no stored rating comes back with rating=None so the card
prints it blank; it is never defaulted to a value nobody gave.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modules.platform import (
    AssessmentDomain, GradingBand, SchoolSection, StudentDomainRating,
)
from app.schemas.platform import CardDomainBlock, CardRatingItem, CardRatingKeyEntry
from app.services.report_sections import report_keys_for

_TITLES = {"affective": "AFFECTIVE DOMAIN", "psychomotor": "PSYCHOMOTOR DOMAIN"}


async def report_key_for_section(db: AsyncSession, org_id: str, section_id: str | None) -> str | None:
    if not section_id:
        return None
    secs = (await db.execute(select(SchoolSection).where(SchoolSection.org_id == org_id))).scalars().all()
    return report_keys_for(secs).get(section_id)


async def card_domain_blocks(
    db: AsyncSession, org_id: str, section_id: str | None, student_id: str, term_id: str,
) -> list[CardDomainBlock]:
    if not section_id:
        return []
    domains = (await db.execute(select(AssessmentDomain).where(
        AssessmentDomain.org_id == org_id, AssessmentDomain.section_id == section_id,
        AssessmentDomain.domain_type.in_(("affective", "psychomotor", "eyfs_area", "eyfs_goal")),
    ).order_by(AssessmentDomain.position, AssessmentDomain.name))).scalars().all()
    if not domains:
        return []
    ratings = {r.domain_id: r for r in (await db.execute(select(StudentDomainRating).where(
        StudentDomainRating.org_id == org_id, StudentDomainRating.student_id == student_id,
        StudentDomainRating.term_id == term_id))).scalars().all()}

    scale_ids = {d.rating_scale_id for d in domains if d.rating_scale_id}
    keys: dict[str, list[CardRatingKeyEntry]] = {}
    if scale_ids:
        for b in (await db.execute(select(GradingBand).where(
                GradingBand.org_id == org_id, GradingBand.scale_id.in_(scale_ids))
                .order_by(GradingBand.position))).scalars().all():
            keys.setdefault(b.scale_id, []).append(CardRatingKeyEntry(label=b.grade, meaning=b.remark))

    def item(d) -> CardRatingItem:
        r = ratings.get(d.id)
        return CardRatingItem(domain_id=d.id, name=d.name,
                              rating=(r.rating if r else None), comment=(r.comment if r else None))

    blocks: list[CardDomainBlock] = []
    for kind in ("affective", "psychomotor"):
        rows = [d for d in domains if d.domain_type == kind]
        if rows:
            blocks.append(CardDomainBlock(
                domain_type=kind, title=_TITLES[kind], items=[item(d) for d in rows],
                key=keys.get(next((d.rating_scale_id for d in rows if d.rating_scale_id), ""), [])))
    goals_by_area: dict[str, list] = {}
    for d in domains:
        if d.domain_type == "eyfs_goal" and d.parent_domain_id:
            goals_by_area.setdefault(d.parent_domain_id, []).append(d)
    for area in (d for d in domains if d.domain_type == "eyfs_area"):
        it = item(area)
        it.children = [item(g) for g in goals_by_area.get(area.id, [])]
        blocks.append(CardDomainBlock(
            domain_type="eyfs_area", title=area.name, items=it.children or [it],
            key=keys.get(area.rating_scale_id or "", [])))
    return blocks
