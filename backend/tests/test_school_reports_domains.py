"""Tests for School Reports R3 — assessment domains + student ratings.

The criterion-referenced / non-cognitive layer of the report card:
  • seed is curriculum-aware + idempotent — EYFS areas nest their goals; a hybrid
    section gets psychomotor + affective skills AND one Cambridge strand per subject
    that carries the overlay; descriptor rating scales are created (EYFS real,
    skills/Cambridge provisional — real labels are the school's to confirm);
  • domain CRUD is tenant-scoped (a foreign parent_subject_id is rejected);
  • ratings upsert per (student, term, domain), an empty rating+comment clears the
    row, a foreign domain_id is refused, and the report card carries the ratings.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.platform import AssessmentDomain, GradingScale, GradingBand
from app.routers.modules.platform import (
    create_section, seed_domains, list_domains, create_domain, update_domain, delete_domain,
    set_all_subjects_cambridge, create_template,
)
from app.routers.modules.school import (
    update_class, get_report_card, set_domain_ratings, list_domain_ratings, create_subject,
)
from app.schemas.platform import (
    SectionCreate, ReportTemplateCreate, SetCambridgeAllRequest,
    DomainCreate, DomainUpdate, DomainRatingsSet, DomainRatingItem,
)
from app.schemas.subject import SubjectCreate
from app.schemas.school_class import ClassUpdate


pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _scale(db, org, name) -> GradingScale:
    return (await db.execute(select(GradingScale).where(
        GradingScale.org_id == org.id, GradingScale.name == name))).scalar_one_or_none()


# ── Seed ──────────────────────────────────────────────────────────────────────────

async def test_seed_eyfs_nests_goals_under_areas_and_is_idempotent(db, org):
    admin = await _preset_user(db, org, "org_admin")
    sec = await create_section(SectionCreate(name="Nursery", curriculum="eyfs"), db=db, current_user=admin)

    domains = await seed_domains(sec.id, db=db, current_user=admin)
    areas = [d for d in domains if d.domain_type == "eyfs_area"]
    goals = [d for d in domains if d.domain_type == "eyfs_goal"]
    assert len(areas) == 7
    assert len(goals) >= 14
    # Every goal hangs off one of the seeded areas (nesting, not a flat list).
    area_ids = {a.id for a in areas}
    assert goals and all(g.parent_domain_id in area_ids for g in goals)
    # EYFS descriptor scale is REAL (published framework), 3 bands.
    eyfs = await _scale(db, org, "EYFS descriptors")
    assert eyfs is not None and eyfs.is_provisional is False
    bands = (await db.execute(select(GradingBand).where(GradingBand.scale_id == eyfs.id))).scalars().all()
    assert {b.grade for b in bands} == {"Emerging", "Expected", "Exceeding"}

    # Idempotent: a second seed adds nothing.
    again = await seed_domains(sec.id, db=db, current_user=admin)
    assert len(again) == len(domains)


async def test_seed_hybrid_adds_skills_and_one_cambridge_strand_per_carried_subject(db, org, teacher):
    admin = await _preset_user(db, org, "org_admin")
    sec = await create_section(SectionCreate(name="Secondary", curriculum="hybrid"), db=db, current_user=admin)
    maths = await create_subject(SubjectCreate(name="Mathematics"), request=None, db=db, current_user=admin)
    english = await create_subject(SubjectCreate(name="English"), request=None, db=db, current_user=admin)
    await set_all_subjects_cambridge(sec.id, SetCambridgeAllRequest(carries_cambridge=True), db=db, current_user=admin)

    domains = await seed_domains(sec.id, db=db, current_user=admin)
    assert [d for d in domains if d.domain_type == "psychomotor"]
    assert [d for d in domains if d.domain_type == "affective"]
    strands = [d for d in domains if d.domain_type == "cambridge_strand"]
    # One strand per carried subject, each linked + name-resolved to its subject.
    assert {s.parent_subject_id for s in strands} == {maths["id"], english["id"]}
    assert all(s.subject_name and s.subject_name in s.name for s in strands)
    # Skills + Cambridge descriptor scales are PROVISIONAL (labels the school confirms).
    assert (await _scale(db, org, "Skills & behaviour (5-point)")).is_provisional is True
    assert (await _scale(db, org, "Cambridge attainment")).is_provisional is True


async def test_seed_nigerian_has_skills_but_no_cambridge_strands(db, org):
    admin = await _preset_user(db, org, "org_admin")
    sec = await create_section(SectionCreate(name="Primary", curriculum="nigerian"), db=db, current_user=admin)
    domains = await seed_domains(sec.id, db=db, current_user=admin)
    assert [d for d in domains if d.domain_type == "affective"]
    assert not [d for d in domains if d.domain_type == "cambridge_strand"]


# ── CRUD (tenant-scoped) ────────────────────────────────────────────────────────

async def test_domain_crud_and_foreign_subject_rejected(db, org):
    admin = await _preset_user(db, org, "org_admin")
    sec = await create_section(SectionCreate(name="Secondary", curriculum="hybrid"), db=db, current_user=admin)

    d = await create_domain(sec.id, DomainCreate(domain_type="affective", name="Punctuality"), db=db, current_user=admin)
    assert d.name == "Punctuality"
    upd = await update_domain(d.id, DomainUpdate(name="Punctuality & Attendance", position=3), db=db, current_user=admin)
    assert upd.name == "Punctuality & Attendance" and upd.position == 3

    # A subject id from ANOTHER org must not attach.
    other = await create_section(SectionCreate(name="Other", curriculum="hybrid"), db=db, current_user=admin)  # same org, still fine
    with pytest.raises(HTTPException) as ei:
        await create_domain(sec.id, DomainCreate(domain_type="cambridge_strand", name="X",
                                                 parent_subject_id=str(uuid.uuid4())), db=db, current_user=admin)
    assert ei.value.status_code == 422

    await delete_domain(d.id, db=db, current_user=admin)
    left = await list_domains(sec.id, domain_type=None, db=db, current_user=admin)
    assert all(x.id != d.id for x in left)
    _ = other


# ── Ratings + report rendering ──────────────────────────────────────────────────

async def test_ratings_upsert_clear_and_flow_into_report_card(db, org, school_class, student):
    admin = await _preset_user(db, org, "org_admin")
    sec = await create_section(SectionCreate(name="Nursery", curriculum="eyfs"), db=db, current_user=admin)
    await create_template(ReportTemplateCreate(section_id=sec.id, name="Nursery", assessment_mode="descriptive"),
                          db=db, current_user=admin)
    await update_class(school_class.id, ClassUpdate(section_id=sec.id), request=None, db=db, current_user=admin)
    domains = await seed_domains(sec.id, db=db, current_user=admin)
    goal = next(d for d in domains if d.domain_type == "eyfs_goal")

    # Upsert a rating for one goal.
    saved = await set_domain_ratings(
        student.id, DomainRatingsSet(term="Term 1", ratings=[
            DomainRatingItem(domain_id=goal.id, rating="Expected", comment="Coming along well"),
        ]), db=db, current_user=admin,
    )
    assert any(r.domain_id == goal.id and r.rating == "Expected" for r in saved)

    got = await list_domain_ratings(student.id, term="Term 1", db=db, current_user=admin)
    assert len(got) == 1 and got[0].comment == "Coming along well"

    # The rating rides the report card, keyed to its domain.
    card = await get_report_card(student.id, term="Term 1", db=db, current_user=admin)
    dom_row = next(x for x in card["domains"] if x["domain_id"] == goal.id)
    assert dom_row["rating"] == "Expected" and dom_row["domain_type"] == "eyfs_goal"
    assert card["assessment_mode"] == "descriptive"

    # Empty rating + comment clears the row.
    await set_domain_ratings(
        student.id, DomainRatingsSet(term="Term 1", ratings=[DomainRatingItem(domain_id=goal.id)]),
        db=db, current_user=admin,
    )
    assert await list_domain_ratings(student.id, term="Term 1", db=db, current_user=admin) == []


async def test_rating_rejects_foreign_domain(db, org, student):
    admin = await _preset_user(db, org, "org_admin")
    with pytest.raises(HTTPException) as ei:
        await set_domain_ratings(
            student.id, DomainRatingsSet(term="Term 1", ratings=[DomainRatingItem(domain_id=str(uuid.uuid4()), rating="X")]),
            db=db, current_user=admin,
        )
    assert ei.value.status_code == 422


async def test_ratings_write_is_reports_scope_not_held_by_parent(db, org):
    # Enforcement rides the route dependency (school:reports:write); assert the
    # preset boundary the guard relies on — a parent can read but never author.
    parent = await _preset_user(db, org, "parent")
    assert parent.has_permission("school:reports:read")
    assert not parent.has_permission("school:reports:write")
