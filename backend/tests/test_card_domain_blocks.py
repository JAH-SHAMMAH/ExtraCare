"""Phase E: rated blocks (behaviour, skills, Early Learning Goals) on the card payload."""
from __future__ import annotations

import uuid

import pytest

from app.models.modules.platform import (
    AcademicTerm, AssessmentDomain, GradingBand, GradingScale, SchoolSection, StudentDomainRating,
)
from app.models.modules.school import SchoolClass, Student
from app.services.card_ratings import card_domain_blocks, report_key_for_section

pytestmark = pytest.mark.asyncio


async def _scale(db, org, name, labels):
    sc = GradingScale(id=str(uuid.uuid4()), name=name, scale_type="descriptor", purpose="keys",
                      is_provisional=False, org_id=org.id)
    db.add(sc)
    await db.flush()
    for i, (lab, meaning) in enumerate(labels):
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade=lab, remark=meaning, position=i, org_id=org.id))
    return sc


async def _world(db, org):
    early = SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Early Years", curriculum="eyfs", position=0)
    prim = SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Primary", curriculum="nigerian", position=1)
    sec = SchoolSection(id=str(uuid.uuid4()), org_id=org.id, name="Secondary", curriculum="nigerian", position=2)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 5", level="YEAR 5", org_id=org.id)
    stu = Student(id=str(uuid.uuid4()), student_id="P/1", first_name="A", last_name="B", class_id=cls.id, org_id=org.id)
    db.add_all([early, prim, sec, term, cls, stu])
    await db.flush()
    return early, prim, sec, term, stu


async def test_report_key_by_curriculum_and_position(db, org):
    early, prim, sec, *_ = await _world(db, org)
    assert await report_key_for_section(db, org.id, early.id) == "nursery-report"
    assert await report_key_for_section(db, org.id, prim.id) == "junior-report"
    assert await report_key_for_section(db, org.id, sec.id) == "secondary-report"
    assert await report_key_for_section(db, org.id, None) is None


async def test_affective_and_psychomotor_blocks_with_key_and_blank_ratings(db, org):
    _e, prim, _s, term, stu = await _world(db, org)
    scale = await _scale(db, org, "5-point", [("5", "Excellent"), ("4", "Very Good"), ("3", "Good")])
    punct = AssessmentDomain(id=str(uuid.uuid4()), org_id=org.id, section_id=prim.id, domain_type="affective",
                             name="Punctuality", rating_scale_id=scale.id, position=0)
    neat = AssessmentDomain(id=str(uuid.uuid4()), org_id=org.id, section_id=prim.id, domain_type="affective",
                            name="Neatness", rating_scale_id=scale.id, position=1)
    hand = AssessmentDomain(id=str(uuid.uuid4()), org_id=org.id, section_id=prim.id, domain_type="psychomotor",
                            name="Handwriting", rating_scale_id=scale.id, position=0)
    db.add_all([punct, neat, hand])
    db.add(StudentDomainRating(id=str(uuid.uuid4()), org_id=org.id, student_id=stu.id, term_id=term.id,
                               domain_id=punct.id, rating="5"))
    await db.commit()
    blocks = await card_domain_blocks(db, org.id, prim.id, stu.id, term.id, "junior-report")
    by = {b.domain_type: b for b in blocks}
    assert by["affective"].title == "AFFECTIVE" and by["psychomotor"].title == "PSYCHOMOTOR"
    sec_blocks = await card_domain_blocks(db, org.id, prim.id, stu.id, term.id, "secondary-report")
    assert {b.title for b in sec_blocks} == {"SKILLS AND BEHAVIOUR"}
    assert [i.name for i in by["affective"].items] == ["Punctuality", "Neatness"]
    assert by["affective"].items[0].rating == "5"
    assert by["affective"].items[1].rating is None            # unrated stays blank, never defaulted
    assert [k.label for k in by["affective"].key] == ["5", "4", "3"]
    assert by["psychomotor"].items[0].name == "Handwriting"


async def test_nursery_areas_carry_their_goals(db, org):
    early, _p, _s, term, stu = await _world(db, org)
    scale = await _scale(db, org, "A/E/SNS", [("A", "Achieved"), ("E", "Emerging"), ("SNS", "Support needed")])
    area = AssessmentDomain(id=str(uuid.uuid4()), org_id=org.id, section_id=early.id, domain_type="eyfs_area",
                            name="Communication and Language", rating_scale_id=scale.id, position=0)
    db.add(area)
    await db.flush()
    g1 = AssessmentDomain(id=str(uuid.uuid4()), org_id=org.id, section_id=early.id, domain_type="eyfs_goal",
                          name="Listening", parent_domain_id=area.id, rating_scale_id=scale.id, position=0)
    g2 = AssessmentDomain(id=str(uuid.uuid4()), org_id=org.id, section_id=early.id, domain_type="eyfs_goal",
                          name="Speaking", parent_domain_id=area.id, rating_scale_id=scale.id, position=1)
    db.add_all([g1, g2])
    db.add(StudentDomainRating(id=str(uuid.uuid4()), org_id=org.id, student_id=stu.id, term_id=term.id,
                               domain_id=g2.id, rating="E", comment="Building sentences"))
    await db.commit()
    blocks = await card_domain_blocks(db, org.id, early.id, stu.id, term.id)
    assert len(blocks) == 1 and blocks[0].title == "Communication and Language"
    assert [(i.name, i.rating) for i in blocks[0].items] == [("Listening", None), ("Speaking", "E")]
    assert blocks[0].items[1].comment == "Building sentences"
    assert [k.label for k in blocks[0].key] == ["A", "E", "SNS"]


async def test_other_sections_and_other_terms_do_not_leak(db, org):
    early, prim, _s, term, stu = await _world(db, org)
    d = AssessmentDomain(id=str(uuid.uuid4()), org_id=org.id, section_id=prim.id, domain_type="affective",
                         name="Punctuality", position=0)
    db.add(d)
    other = AcademicTerm(id=str(uuid.uuid4()), name="Spring", position=2, org_id=org.id)
    db.add(other)
    await db.flush()
    db.add(StudentDomainRating(id=str(uuid.uuid4()), org_id=org.id, student_id=stu.id, term_id=other.id,
                               domain_id=d.id, rating="5"))
    await db.commit()
    assert await card_domain_blocks(db, org.id, early.id, stu.id, term.id) == []     # Nursery has none
    got = await card_domain_blocks(db, org.id, prim.id, stu.id, term.id)
    assert got[0].items[0].rating is None                                           # Spring's rating is not Autumn's


async def test_photo_rides_with_the_rating(db, org):
    early, _p, _s, term, stu = await _world(db, org)
    area = AssessmentDomain(id=str(uuid.uuid4()), org_id=org.id, section_id=early.id, domain_type="eyfs_area",
                            name="Literacy", position=0)
    db.add(area)
    await db.flush()
    g = AssessmentDomain(id=str(uuid.uuid4()), org_id=org.id, section_id=early.id, domain_type="eyfs_goal",
                         name="Writing", parent_domain_id=area.id, position=0)
    db.add(g)
    db.add(StudentDomainRating(id=str(uuid.uuid4()), org_id=org.id, student_id=stu.id, term_id=term.id,
                               domain_id=g.id, comment="Writes her name", photo_url="https://x/y.jpg"))
    await db.commit()
    blocks = await card_domain_blocks(db, org.id, early.id, stu.id, term.id)
    assert blocks[0].items[0].photo_url == "https://x/y.jpg"
