"""
Behaviour & Skills assessment domain management and student rating entry.

Endpoints for admin setup (domain CRUD) and teacher data entry (rating upsert).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.deps import get_current_active_user
from app.models.modules.platform import AssessmentDomain, GradingScale, StudentDomainRating, AcademicTerm, SchoolSection
from app.models.modules.school import Student
from app.core.tenant import require_role_module

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_role_module("school"))],
)

# ── Request/Response Models ────────────────────────────────────────────────

class DomainCreate(BaseModel):
    """Create a new assessment domain."""
    section_id: str = Field(..., description="SchoolSection ID (Nursery, Primary, Secondary, etc)")
    domain_type: str = Field(..., description="psychomotor | affective")
    name: str = Field(..., description="Domain name (e.g., Communication, Teamwork)")
    rating_scale_id: str | None = Field(None, description="FK to GradingScale for rating descriptors")
    position: int = Field(default=0, description="Sort order")


class DomainUpdate(BaseModel):
    """Update an assessment domain."""
    name: str | None = None
    rating_scale_id: str | None = None
    position: int | None = None


class DomainResponse(BaseModel):
    """Serialized AssessmentDomain."""
    id: str
    section_id: str
    domain_type: str
    name: str
    rating_scale_id: str | None
    position: int

    class Config:
        from_attributes = True


class StudentRatingCreate(BaseModel):
    """One student's rating for one domain."""
    domain_id: str
    rating: str | None = Field(None, description="Descriptor label (e.g., 'Excellent')")
    comment: str | None = Field(None, description="Optional teacher notes")


class StudentRatingResponse(BaseModel):
    """Serialized StudentDomainRating."""
    id: str
    student_id: str
    term: str
    domain_id: str
    rating: str | None
    comment: str | None

    class Config:
        from_attributes = True


class StudentRatingBulk(BaseModel):
    """Bulk upsert ratings for one student."""
    ratings: list[StudentRatingCreate] = Field(..., description="Array of domain ratings")
    term: str = Field(..., description="Academic term (e.g., 'Term 1')")


# ── Dependencies ───────────────────────────────────────────────────────────

async def _require_setup_write(current_user: User = Depends(get_current_active_user)) -> User:
    """Require settings:write permission for domain CRUD."""
    if not current_user.has_permission("settings:write"):
        raise HTTPException(status_code=403, detail="Permission denied: settings:write required")
    return current_user


async def _require_reports_write(current_user: User = Depends(get_current_active_user)) -> User:
    """Require school:assessments:write for rating entry."""
    if not current_user.has_permission("school:assessments:write"):
        raise HTTPException(status_code=403, detail="Permission denied: school:assessments:write required")
    return current_user


async def _require_reports_read(current_user: User = Depends(get_current_active_user)) -> User:
    """Require school:assessments:read for viewing ratings."""
    if not current_user.has_permission("school:assessments:read"):
        raise HTTPException(status_code=403, detail="Permission denied: school:assessments:read required")
    return current_user


# ── Endpoints: Domain CRUD ─────────────────────────────────────────────────

@router.get("/domains", dependencies=[Depends(_require_reports_read)])
async def list_domains(
    section_id: str | None = None,
    domain_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[DomainResponse]:
    """List assessment domains, optionally filtered by section and/or type."""
    query = select(AssessmentDomain).where(AssessmentDomain.org_id == current_user.org_id)

    if section_id:
        query = query.where(AssessmentDomain.section_id == section_id)
    if domain_type:
        query = query.where(AssessmentDomain.domain_type == domain_type)

    query = query.order_by(AssessmentDomain.position)
    domains = (await db.execute(query)).scalars().all()
    return [DomainResponse.from_orm(d) for d in domains]


@router.post("/domains", dependencies=[Depends(_require_setup_write)])
async def create_domain(
    payload: DomainCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DomainResponse:
    """Create a new assessment domain."""
    # Verify section exists
    section = await db.get(SchoolSection, payload.section_id)
    if not section or section.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="SchoolSection not found")

    # Verify rating_scale exists if provided
    if payload.rating_scale_id:
        scale = await db.get(GradingScale, payload.rating_scale_id)
        if not scale or scale.org_id != current_user.org_id:
            raise HTTPException(status_code=404, detail="GradingScale not found")

    domain = AssessmentDomain(
        org_id=current_user.org_id,
        section_id=payload.section_id,
        domain_type=payload.domain_type,
        name=payload.name,
        rating_scale_id=payload.rating_scale_id,
        position=payload.position,
    )
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return DomainResponse.from_orm(domain)


@router.put("/domains/{domain_id}", dependencies=[Depends(_require_setup_write)])
async def update_domain(
    domain_id: str,
    payload: DomainUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DomainResponse:
    """Update an assessment domain."""
    domain = await db.get(AssessmentDomain, domain_id)
    if not domain or domain.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Domain not found")

    # Verify new rating_scale if provided
    if payload.rating_scale_id is not None:
        scale = await db.get(GradingScale, payload.rating_scale_id)
        if not scale or scale.org_id != current_user.org_id:
            raise HTTPException(status_code=404, detail="GradingScale not found")

    if payload.name is not None:
        domain.name = payload.name
    if payload.rating_scale_id is not None:
        domain.rating_scale_id = payload.rating_scale_id
    if payload.position is not None:
        domain.position = payload.position

    await db.commit()
    await db.refresh(domain)
    return DomainResponse.from_orm(domain)


@router.delete("/domains/{domain_id}", dependencies=[Depends(_require_setup_write)])
async def delete_domain(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Delete an assessment domain (cascade to StudentDomainRatings)."""
    domain = await db.get(AssessmentDomain, domain_id)
    if not domain or domain.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Domain not found")

    await db.delete(domain)
    await db.commit()
    return {"deleted": True}


# ── Endpoints: Student Domain Ratings ──────────────────────────────────────

@router.get("/students/{student_id}/domain-ratings", dependencies=[Depends(_require_reports_read)])
async def get_student_ratings(
    student_id: str,
    term: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[StudentRatingResponse]:
    """Get all domain ratings for a student, optionally filtered by term."""
    # Verify student exists and is visible to user
    student = await db.get(Student, student_id)
    if not student or student.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Student not found")

    query = select(StudentDomainRating).where(
        StudentDomainRating.org_id == current_user.org_id,
        StudentDomainRating.student_id == student_id,
    )

    if term:
        query = query.where(StudentDomainRating.term == term)

    ratings = (await db.execute(query)).scalars().all()
    return [StudentRatingResponse.from_orm(r) for r in ratings]


@router.post("/students/{student_id}/domain-ratings/bulk", dependencies=[Depends(_require_reports_write)])
async def upsert_student_ratings(
    student_id: str,
    payload: StudentRatingBulk,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Upsert (create or update) multiple domain ratings for a student in a term."""
    # Verify student exists
    student = await db.get(Student, student_id)
    if not student or student.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Student not found")

    # Verify term exists
    term_obj = (await db.execute(
        select(AcademicTerm).where(
            AcademicTerm.org_id == current_user.org_id,
            AcademicTerm.name == payload.term
        )
    )).scalar_one_or_none()
    if not term_obj:
        raise HTTPException(status_code=404, detail="Academic term not found")

    upserted = 0
    for rating_data in payload.ratings:
        # Verify domain exists
        domain = await db.get(AssessmentDomain, rating_data.domain_id)
        if not domain or domain.org_id != current_user.org_id:
            raise HTTPException(status_code=404, detail=f"Domain {rating_data.domain_id} not found")

        # Upsert: try to find existing rating
        existing = (await db.execute(
            select(StudentDomainRating).where(
                StudentDomainRating.student_id == student_id,
                StudentDomainRating.term == payload.term,
                StudentDomainRating.domain_id == rating_data.domain_id,
                StudentDomainRating.org_id == current_user.org_id,
            )
        )).scalar_one_or_none()

        if existing:
            # Update
            existing.rating = rating_data.rating
            existing.comment = rating_data.comment
        else:
            # Create
            rating = StudentDomainRating(
                org_id=current_user.org_id,
                student_id=student_id,
                term=payload.term,
                domain_id=rating_data.domain_id,
                rating=rating_data.rating,
                comment=rating_data.comment,
            )
            db.add(rating)

        upserted += 1

    await db.commit()
    return {"upserted": upserted}
