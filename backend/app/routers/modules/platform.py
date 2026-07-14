"""Administration & Platform router (Batch 7), prefix ``/platform``.

School Setup, Custom Fields, Voting, Mailbox (announcements), Mobile Manager.
Admin config is ``settings:*``; per-user surfaces (mailbox inbox, registering a
mobile device, reading app config) are authenticated-only so end users can use
them. Voting integrity: one vote per (poll, voter) is DB-enforced and results
are derived from votes, never a mutable tally.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_module
from app.core.permissions import PermissionChecker
from app.models.user import User, UserStatus
from app.models.modules.platform import (
    AcademicSession, AcademicWeek, SchoolHouse, GradingBand,
    SchoolSection, GradingScale, ReportTemplate, ReportSubjectAssessment,
    AssessmentDomain,
    CustomFieldDefinition, CustomFieldValue,
    Poll, PollOption, PollVote,
    MailboxMessage, MailboxRecipient,
    MobileDevice, MobileAppConfig,
)
from app.models.modules.school import SchoolClass, Subject
from app.schemas.platform import (
    SessionCreate, SessionUpdate, SessionResponse, CurrentSessionResponse,
    HouseCreate, HouseResponse, BandCreate, BandResponse,
    WeekCreate, WeekUpdate, WeekGenerate, WeekResponse,
    FieldDefCreate, FieldDefResponse, FieldValueSet, FieldValueResponse,
    PollCreate, PollResponse, PollOptionResult, PollListResponse, CastVote,
    MessageCreate, MessageResponse, InboxItemResponse,
    MobileDeviceRegister, MobileDeviceResponse, AppConfigSet, AppConfigResponse,
    SectionCreate, SectionUpdate, SectionResponse,
    GradingScaleCreate, GradingScaleResponse, ScaleBandCreate,
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateResponse, AutoMapResult,
    SubjectAssessmentResponse, SubjectAssessmentUpdate, SetCambridgeAllRequest,
    DomainCreate, DomainUpdate, DomainResponse, DOMAIN_TYPES,
    SECTION_CURRICULA, ASSESSMENT_MODES, SCALE_TYPES,
)
from app.services.ledger import money  # Decimal helper for grading bands

router = APIRouter(prefix="/platform", tags=["Administration & Platform"], dependencies=[Depends(require_module("school"))])

_read = Depends(PermissionChecker("settings:read"))
_write = Depends(PermissionChecker("settings:write"))
# The current-session resolver is read by term-consuming features (exam/grade/CBT
# forms), so it rides the broad school:read rather than the admin settings scope.
_school_read = Depends(PermissionChecker("school:read"))


# ── School Setup ────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[SessionResponse], dependencies=[_read])
async def list_sessions(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(AcademicSession).where(AcademicSession.org_id == current_user.org_id).order_by(AcademicSession.start_date.desc()))).scalars().all()
    return [SessionResponse(id=s.id, name=s.name, term=s.term, start_date=s.start_date, end_date=s.end_date, is_current=s.is_current, created_at=s.created_at, org_id=s.org_id) for s in rows]


def _session_response(s: AcademicSession) -> SessionResponse:
    return SessionResponse(id=s.id, name=s.name, term=s.term, start_date=s.start_date,
                           end_date=s.end_date, is_current=s.is_current, created_at=s.created_at, org_id=s.org_id)


@router.get("/sessions/current", response_model=CurrentSessionResponse, dependencies=[_school_read])
async def current_session(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """The org's current session/term, for term-consuming forms to default from.
    Broadly readable (school:read); null when nothing is marked current."""
    s = (await db.execute(
        select(AcademicSession).where(
            AcademicSession.org_id == current_user.org_id, AcademicSession.is_current == True)
    )).scalars().first()
    if not s:
        return CurrentSessionResponse()
    return CurrentSessionResponse(session=_session_response(s), term=s.term, name=s.name)


@router.post("/sessions", response_model=SessionResponse, status_code=201, dependencies=[_write])
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.is_current:
        await db.execute(update(AcademicSession).where(AcademicSession.org_id == current_user.org_id).values(is_current=False))
    s = AcademicSession(**payload.model_dump(), org_id=current_user.org_id)
    db.add(s)
    await db.flush()
    return _session_response(s)


@router.patch("/sessions/{session_id}", response_model=SessionResponse, dependencies=[_write])
async def update_session(session_id: str, payload: SessionUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(
        select(AcademicSession).where(AcademicSession.id == session_id, AcademicSession.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found.")
    changes = payload.model_dump(exclude_unset=True)
    # Marking this one current unsets every other session in the org (single-current).
    if changes.get("is_current") is True:
        await db.execute(update(AcademicSession).where(
            AcademicSession.org_id == current_user.org_id, AcademicSession.id != session_id
        ).values(is_current=False))
    for field, value in changes.items():
        setattr(s, field, value)
    await db.flush()
    return _session_response(s)


@router.delete("/sessions/{session_id}", status_code=204, dependencies=[_write])
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(select(AcademicSession).where(AcademicSession.id == session_id, AcademicSession.org_id == current_user.org_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found.")
    await db.delete(s)


@router.get("/houses", response_model=list[HouseResponse], dependencies=[_read])
async def list_houses(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(SchoolHouse).where(SchoolHouse.org_id == current_user.org_id).order_by(SchoolHouse.name))).scalars().all()
    return [HouseResponse(id=h.id, name=h.name, color=h.color, motto=h.motto, created_at=h.created_at, org_id=h.org_id) for h in rows]


@router.post("/houses", response_model=HouseResponse, status_code=201, dependencies=[_write])
async def create_house(payload: HouseCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    h = SchoolHouse(**payload.model_dump(), org_id=current_user.org_id)
    db.add(h)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A house with that name already exists.")
    return HouseResponse(id=h.id, name=h.name, color=h.color, motto=h.motto, created_at=h.created_at, org_id=h.org_id)


@router.delete("/houses/{house_id}", status_code=204, dependencies=[_write])
async def delete_house(house_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    h = (await db.execute(select(SchoolHouse).where(SchoolHouse.id == house_id, SchoolHouse.org_id == current_user.org_id))).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="House not found.")
    await db.delete(h)


def _band_response(b: GradingBand) -> BandResponse:
    return BandResponse(
        id=b.id, grade=b.grade,
        min_score=float(b.min_score) if b.min_score is not None else None,
        max_score=float(b.max_score) if b.max_score is not None else None,
        remark=b.remark, scale_id=b.scale_id, position=b.position or 0,
        created_at=b.created_at, org_id=b.org_id,
    )


@router.get("/grading-bands", response_model=list[BandResponse], dependencies=[_read])
async def list_bands(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Legacy flat listing (scale-less bands). Scale-scoped bands come back with the scale.
    rows = (await db.execute(
        select(GradingBand).where(GradingBand.org_id == current_user.org_id, GradingBand.scale_id.is_(None))
        .order_by(GradingBand.min_score.desc())
    )).scalars().all()
    return [_band_response(b) for b in rows]


@router.post("/grading-bands", response_model=BandResponse, status_code=201, dependencies=[_write])
async def create_band(payload: BandCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.max_score < payload.min_score:
        raise HTTPException(status_code=422, detail="max_score must be ≥ min_score.")
    b = GradingBand(grade=payload.grade, min_score=money(payload.min_score), max_score=money(payload.max_score), remark=payload.remark, org_id=current_user.org_id)
    db.add(b)
    await db.flush()
    return _band_response(b)


@router.delete("/grading-bands/{band_id}", status_code=204, dependencies=[_write])
async def delete_band(band_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    b = (await db.execute(select(GradingBand).where(GradingBand.id == band_id, GradingBand.org_id == current_user.org_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Band not found.")
    await db.delete(b)


# ── School Reports R2: sections ───────────────────────────────────────────────────

def _norm_level(x) -> str:
    """Normalize a level/section label for matching: trim, collapse whitespace, casefold."""
    return " ".join((x or "").split()).casefold()


def _clean_aliases(aliases) -> list[str]:
    seen, out = set(), []
    for a in (aliases or []):
        a = (a or "").strip()
        k = _norm_level(a)
        if a and k not in seen:
            seen.add(k)
            out.append(a)
    return out


def _section_response(s: SchoolSection) -> SectionResponse:
    return SectionResponse(id=s.id, name=s.name, curriculum=s.curriculum, position=s.position,
                           aliases=s.level_aliases or [], org_id=s.org_id)


# Readable at the broad school:read (not just settings:read): sections are report
# reference data the level report views + term-consuming forms resolve. Writes stay
# settings:write. Mirrors the current-session resolver's broad-read rationale.
@router.get("/sections", response_model=list[SectionResponse], dependencies=[_school_read])
async def list_sections(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(SchoolSection).where(SchoolSection.org_id == current_user.org_id).order_by(SchoolSection.position, SchoolSection.name)
    )).scalars().all()
    return [_section_response(s) for s in rows]


@router.post("/sections", response_model=SectionResponse, status_code=201, dependencies=[_write])
async def create_section(payload: SectionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.curriculum not in SECTION_CURRICULA:
        raise HTTPException(status_code=422, detail=f"curriculum must be one of {sorted(SECTION_CURRICULA)}")
    s = SchoolSection(name=payload.name.strip(), curriculum=payload.curriculum, position=payload.position,
                      level_aliases=_clean_aliases(payload.aliases) or None, org_id=current_user.org_id)
    db.add(s)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Section '{payload.name}' already exists.")
    return _section_response(s)


@router.patch("/sections/{section_id}", response_model=SectionResponse, dependencies=[_write])
async def update_section(section_id: str, payload: SectionUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(select(SchoolSection).where(SchoolSection.id == section_id, SchoolSection.org_id == current_user.org_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Section not found.")
    data = payload.model_dump(exclude_unset=True)
    if "curriculum" in data and data["curriculum"] not in SECTION_CURRICULA:
        raise HTTPException(status_code=422, detail=f"curriculum must be one of {sorted(SECTION_CURRICULA)}")
    if "aliases" in data:
        s.level_aliases = _clean_aliases(data.pop("aliases")) or None
    for f, v in data.items():
        setattr(s, f, v)
    await db.flush()
    return _section_response(s)


@router.delete("/sections/{section_id}", status_code=204, dependencies=[_write])
async def delete_section(section_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(select(SchoolSection).where(SchoolSection.id == section_id, SchoolSection.org_id == current_user.org_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Section not found.")
    await db.delete(s)   # classes.section_id → SET NULL; templates → CASCADE


@router.post("/sections/auto-map", response_model=AutoMapResult, dependencies=[_write])
async def auto_map_sections(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Link each currently-unassigned class to a section by a NORMALIZED match
    (trim + collapse whitespace + casefold) of its free-text `level` against the
    section name OR any of the section's level aliases. Blank / typo / unknown
    levels are left unassigned — never guessed. Returns the count linked and the
    class names left unmatched."""
    sections = (await db.execute(select(SchoolSection).where(SchoolSection.org_id == current_user.org_id))).scalars().all()
    by_norm = {}
    for s in sections:
        for label in [s.name, *(s.level_aliases or [])]:
            k = _norm_level(label)
            if k:
                by_norm.setdefault(k, s.id)   # first section wins on any collision
    classes = (await db.execute(
        select(SchoolClass).where(SchoolClass.org_id == current_user.org_id, SchoolClass.section_id.is_(None))
    )).scalars().all()
    linked, unassigned = 0, []
    for c in classes:
        key = _norm_level(c.level)
        sid = by_norm.get(key) if key else None
        if sid:
            c.section_id = sid
            linked += 1
        else:
            unassigned.append(c.name)
    await db.flush()
    return AutoMapResult(linked=linked, unassigned=unassigned)


# ── School Reports R2: grading scales ─────────────────────────────────────────────

def _scale_response(scale: GradingScale, bands: list[GradingBand]) -> GradingScaleResponse:
    ordered = sorted(bands, key=lambda b: (b.position or 0))
    return GradingScaleResponse(
        id=scale.id, name=scale.name, scale_type=scale.scale_type, is_provisional=scale.is_provisional,
        bands=[_band_response(b) for b in ordered], org_id=scale.org_id,
    )


@router.get("/grading-scales", response_model=list[GradingScaleResponse], dependencies=[_read])
async def list_scales(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    scales = (await db.execute(select(GradingScale).where(GradingScale.org_id == current_user.org_id).order_by(GradingScale.name))).scalars().all()
    band_rows = (await db.execute(select(GradingBand).where(GradingBand.org_id == current_user.org_id, GradingBand.scale_id.is_not(None)))).scalars().all()
    by_scale: dict[str, list[GradingBand]] = {}
    for b in band_rows:
        by_scale.setdefault(b.scale_id, []).append(b)
    return [_scale_response(s, by_scale.get(s.id, [])) for s in scales]


@router.post("/grading-scales", response_model=GradingScaleResponse, status_code=201, dependencies=[_write])
async def create_scale(payload: GradingScaleCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.scale_type not in SCALE_TYPES:
        raise HTTPException(status_code=422, detail=f"scale_type must be one of {sorted(SCALE_TYPES)}")
    scale = GradingScale(name=payload.name.strip(), scale_type=payload.scale_type, is_provisional=payload.is_provisional, org_id=current_user.org_id)
    db.add(scale)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Scale '{payload.name}' already exists.")
    bands = []
    for i, bd in enumerate(payload.bands):
        b = GradingBand(
            scale_id=scale.id, grade=bd.grade,
            min_score=money(bd.min_score) if bd.min_score is not None else None,
            max_score=money(bd.max_score) if bd.max_score is not None else None,
            remark=bd.remark, position=bd.position or i, org_id=current_user.org_id,
        )
        db.add(b)
        bands.append(b)
    await db.flush()
    return _scale_response(scale, bands)


@router.put("/grading-scales/{scale_id}/bands", response_model=GradingScaleResponse, dependencies=[_write])
async def replace_scale_bands(scale_id: str, bands: list[ScaleBandCreate], db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Replace a scale's bands wholesale — the simplest correct edit for a small,
    ordered band set (no per-row diffing). Locking the school's real boundaries is
    this call, not a migration."""
    scale = (await db.execute(select(GradingScale).where(GradingScale.id == scale_id, GradingScale.org_id == current_user.org_id))).scalar_one_or_none()
    if not scale:
        raise HTTPException(status_code=404, detail="Scale not found.")
    existing = (await db.execute(select(GradingBand).where(GradingBand.scale_id == scale_id, GradingBand.org_id == current_user.org_id))).scalars().all()
    for b in existing:
        await db.delete(b)
    await db.flush()
    fresh = []
    for i, bd in enumerate(bands):
        b = GradingBand(
            scale_id=scale.id, grade=bd.grade,
            min_score=money(bd.min_score) if bd.min_score is not None else None,
            max_score=money(bd.max_score) if bd.max_score is not None else None,
            remark=bd.remark, position=bd.position or i, org_id=current_user.org_id,
        )
        db.add(b)
        fresh.append(b)
    scale.is_provisional = False   # editing the bands = the school has locked real numbers
    await db.flush()
    return _scale_response(scale, fresh)


@router.delete("/grading-scales/{scale_id}", status_code=204, dependencies=[_write])
async def delete_scale(scale_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    scale = (await db.execute(select(GradingScale).where(GradingScale.id == scale_id, GradingScale.org_id == current_user.org_id))).scalar_one_or_none()
    if not scale:
        raise HTTPException(status_code=404, detail="Scale not found.")
    await db.delete(scale)   # bands CASCADE; templates.grading_scale_id → SET NULL


# ── School Reports R2: report templates ───────────────────────────────────────────

def _template_response(t: ReportTemplate, section_name: str | None, scale_name: str | None) -> ReportTemplateResponse:
    return ReportTemplateResponse(
        id=t.id, section_id=t.section_id, section_name=section_name, name=t.name,
        assessment_mode=t.assessment_mode,
        ca_weight=float(t.ca_weight) if t.ca_weight is not None else None,
        exam_weight=float(t.exam_weight) if t.exam_weight is not None else None,
        grading_scale_id=t.grading_scale_id, grading_scale_name=scale_name,
        show_cognitive_table=t.show_cognitive_table, show_position=t.show_position,
        show_attendance=t.show_attendance, show_affective=t.show_affective,
        show_psychomotor=t.show_psychomotor, is_provisional=t.is_provisional, org_id=t.org_id,
    )


async def _section_and_scale_names(db, org_id, section_ids, scale_ids):
    secs = {s.id: s.name for s in (await db.execute(select(SchoolSection).where(SchoolSection.org_id == org_id, SchoolSection.id.in_({i for i in section_ids if i})))).scalars().all()} if section_ids else {}
    scls = {s.id: s.name for s in (await db.execute(select(GradingScale).where(GradingScale.org_id == org_id, GradingScale.id.in_({i for i in scale_ids if i})))).scalars().all()} if scale_ids else {}
    return secs, scls


@router.get("/report-templates", response_model=list[ReportTemplateResponse], dependencies=[_read])
async def list_templates(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(ReportTemplate).where(ReportTemplate.org_id == current_user.org_id))).scalars().all()
    secs, scls = await _section_and_scale_names(db, current_user.org_id, {t.section_id for t in rows}, {t.grading_scale_id for t in rows})
    return [_template_response(t, secs.get(t.section_id), scls.get(t.grading_scale_id)) for t in rows]


@router.post("/report-templates", response_model=ReportTemplateResponse, status_code=201, dependencies=[_write])
async def create_template(payload: ReportTemplateCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.assessment_mode not in ASSESSMENT_MODES:
        raise HTTPException(status_code=422, detail=f"assessment_mode must be one of {sorted(ASSESSMENT_MODES)}")
    sec = (await db.execute(select(SchoolSection).where(SchoolSection.id == payload.section_id, SchoolSection.org_id == current_user.org_id))).scalar_one_or_none()
    if not sec:
        raise HTTPException(status_code=404, detail="Section not found.")
    t = ReportTemplate(
        section_id=payload.section_id, name=payload.name.strip(), assessment_mode=payload.assessment_mode,
        ca_weight=payload.ca_weight, exam_weight=payload.exam_weight, grading_scale_id=payload.grading_scale_id,
        show_cognitive_table=payload.show_cognitive_table, show_position=payload.show_position,
        show_attendance=payload.show_attendance, show_affective=payload.show_affective,
        show_psychomotor=payload.show_psychomotor, is_provisional=payload.is_provisional, org_id=current_user.org_id,
    )
    db.add(t)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A template already exists for that section.")
    secs, scls = await _section_and_scale_names(db, current_user.org_id, {t.section_id}, {t.grading_scale_id})
    return _template_response(t, secs.get(t.section_id), scls.get(t.grading_scale_id))


@router.patch("/report-templates/{template_id}", response_model=ReportTemplateResponse, dependencies=[_write])
async def update_template(template_id: str, payload: ReportTemplateUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = (await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id, ReportTemplate.org_id == current_user.org_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")
    data = payload.model_dump(exclude_unset=True)
    if "assessment_mode" in data and data["assessment_mode"] not in ASSESSMENT_MODES:
        raise HTTPException(status_code=422, detail=f"assessment_mode must be one of {sorted(ASSESSMENT_MODES)}")
    for f, v in data.items():
        setattr(t, f, v)
    await db.flush()
    secs, scls = await _section_and_scale_names(db, current_user.org_id, {t.section_id}, {t.grading_scale_id})
    return _template_response(t, secs.get(t.section_id), scls.get(t.grading_scale_id))


@router.delete("/report-templates/{template_id}", status_code=204, dependencies=[_write])
async def delete_template(template_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = (await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id, ReportTemplate.org_id == current_user.org_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")
    await db.delete(t)


@router.post("/report-config/bootstrap", response_model=list[ReportTemplateResponse], dependencies=[_write])
async def bootstrap_report_config(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """One-click setup: create/refresh the Nursery / Primary / Secondary sections
    (British curriculum: Year 1–6 Primary, Year 7–12 Secondary) with their level
    aliases, the school's REAL grading scale + bands, and a template per section.
    Idempotent + self-healing: re-running updates templates in place, so an earlier
    provisional seed is replaced by the confirmed constants (one shared A–F scale;
    CA/exam 40/60 for Primary + Secondary; EYFS descriptors for Nursery)."""
    org_id = current_user.org_id
    existing_secs = {s.name.casefold(): s for s in (await db.execute(select(SchoolSection).where(SchoolSection.org_id == org_id))).scalars().all()}
    existing_scales = {s.name.casefold(): s for s in (await db.execute(select(GradingScale).where(GradingScale.org_id == org_id))).scalars().all()}

    def ensure_section(name, curriculum, pos, aliases):
        s = existing_secs.get(name.casefold())
        if not s:
            s = SchoolSection(name=name, curriculum=curriculum, position=pos,
                              level_aliases=_clean_aliases(aliases) or None, org_id=org_id)
            db.add(s)
            existing_secs[name.casefold()] = s
        elif not s.level_aliases:
            s.level_aliases = _clean_aliases(aliases) or None   # backfill aliases onto a pre-existing bare section
        return s

    nursery = ensure_section("Nursery", "eyfs", 0, ["PLAY GROUP", "PRE-NURSERY", "NURSERY", "RECEPTION"])
    primary = ensure_section("Primary", "hybrid", 1, ["YEAR 1", "YEAR 2", "YEAR 3", "YEAR 4", "YEAR 5", "YEAR 6"])
    secondary = ensure_section("Secondary", "hybrid", 2, ["YEAR 7", "YEAR 8", "YEAR 9", "YEAR 10", "YEAR 11", "YEAR 12"])

    # The school's CONFIRMED constants (2026-07-13): ONE shared 5-band A–F scale
    # for both Primary and Secondary (70/60/50/45/40 → A/B/C/D/E, <40 F); CA/exam
    # 40/60 both. EYFS descriptors for Nursery. Non-provisional — real numbers.
    scale_specs = [
        ("Grading Scale (A–F)", "numeric", [
            ("A", 70, 100, "Excellent"), ("B", 60, 69, "Very good"), ("C", 50, 59, "Good"),
            ("D", 45, 49, "Fair"), ("E", 40, 44, "Pass"), ("F", 0, 39, "Fail")]),
        ("EYFS descriptors", "descriptor", [
            ("Emerging", None, None, None), ("Expected", None, None, None), ("Exceeding", None, None, None)]),
    ]
    new_scale_names = set()
    for name, stype, _bands in scale_specs:
        if name.casefold() not in existing_scales:
            s = GradingScale(name=name, scale_type=stype, is_provisional=False, org_id=org_id)
            db.add(s)
            existing_scales[name.casefold()] = s
            new_scale_names.add(name.casefold())
    # Flush so sections AND scales get their ids before we reference them below.
    await db.flush()
    # Bands only for scales we just created (ids now assigned) — idempotent.
    for name, _stype, bands in scale_specs:
        if name.casefold() in new_scale_names:
            s = existing_scales[name.casefold()]
            for i, (grade, lo, hi, remark) in enumerate(bands):
                db.add(GradingBand(scale_id=s.id, grade=grade,
                                   min_score=money(lo) if lo is not None else None,
                                   max_score=money(hi) if hi is not None else None,
                                   remark=remark, position=i, org_id=org_id))
    await db.flush()
    grading_scale = existing_scales["grading scale (a–f)".casefold()]

    # Templates: one per section, UPDATED in place so a re-run replaces any earlier
    # provisional seed with these real values. Primary + Secondary share the scale.
    existing_templates = {t.section_id: t for t in (await db.execute(
        select(ReportTemplate).where(ReportTemplate.org_id == org_id))).scalars().all()}

    def ensure_template(section, name, mode, ca, exam, scale):
        t = existing_templates.get(section.id)
        if not t:
            t = ReportTemplate(section_id=section.id, name=name, org_id=org_id)
            db.add(t)
            existing_templates[section.id] = t
        t.assessment_mode = mode
        t.ca_weight = ca
        t.exam_weight = exam
        t.grading_scale_id = scale.id if scale else None
        t.show_cognitive_table = (mode != "descriptive")
        t.show_position = (mode != "descriptive")
        t.show_attendance = True
        t.show_affective = True
        t.show_psychomotor = (mode == "descriptive")
        t.is_provisional = False
        return t

    ensure_template(nursery, "Nursery (EYFS)", "descriptive", None, None, None)
    ensure_template(primary, "Primary report", "hybrid", 40, 60, grading_scale)
    ensure_template(secondary, "Secondary report", "hybrid", 40, 60, grading_scale)
    await db.flush()

    # R2b: the hybrid sections carry the Cambridge overlay across ALL subjects (the
    # school's confirmed blend). Idempotent upsert for every existing subject.
    subjects = (await db.execute(select(Subject).where(Subject.org_id == org_id))).scalars().all()
    if subjects:
        existing_assess = {(a.section_id, a.subject_id): a for a in (await db.execute(
            select(ReportSubjectAssessment).where(ReportSubjectAssessment.org_id == org_id))).scalars().all()}
        for sec in (primary, secondary):
            for subj in subjects:
                a = existing_assess.get((sec.id, subj.id))
                if not a:
                    db.add(ReportSubjectAssessment(section_id=sec.id, subject_id=subj.id, carries_cambridge=True, org_id=org_id))
                else:
                    a.carries_cambridge = True
        await db.flush()

    rows = (await db.execute(select(ReportTemplate).where(ReportTemplate.org_id == org_id))).scalars().all()
    secs, scls = await _section_and_scale_names(db, org_id, {t.section_id for t in rows}, {t.grading_scale_id for t in rows})
    return [_template_response(t, secs.get(t.section_id), scls.get(t.grading_scale_id)) for t in rows]


# ── School Reports R2b: per-subject Cambridge overlay ─────────────────────────────

async def _require_section(db, section_id, org_id) -> SchoolSection:
    s = (await db.execute(select(SchoolSection).where(SchoolSection.id == section_id, SchoolSection.org_id == org_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Section not found.")
    return s


@router.get("/sections/{section_id}/subjects", response_model=list[SubjectAssessmentResponse], dependencies=[_read])
async def list_section_subjects(section_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Every org subject with its Cambridge-overlay flag for this section (rows that
    don't exist yet default to carries_cambridge=false)."""
    org_id = current_user.org_id
    await _require_section(db, section_id, org_id)
    subjects = (await db.execute(select(Subject).where(Subject.org_id == org_id).order_by(Subject.name))).scalars().all()
    assessments = {a.subject_id: a for a in (await db.execute(
        select(ReportSubjectAssessment).where(ReportSubjectAssessment.org_id == org_id, ReportSubjectAssessment.section_id == section_id)
    )).scalars().all()}
    out = []
    for s in subjects:
        a = assessments.get(s.id)
        out.append(SubjectAssessmentResponse(
            subject_id=s.id, subject_name=s.name,
            carries_cambridge=bool(a.carries_cambridge) if a else False,
            cambridge_scale_id=a.cambridge_scale_id if a else None,
        ))
    return out


async def _upsert_assessment(db, org_id, section_id, subject_id, carries, scale_id):
    a = (await db.execute(select(ReportSubjectAssessment).where(
        ReportSubjectAssessment.org_id == org_id, ReportSubjectAssessment.section_id == section_id,
        ReportSubjectAssessment.subject_id == subject_id,
    ))).scalar_one_or_none()
    if not a:
        a = ReportSubjectAssessment(section_id=section_id, subject_id=subject_id, org_id=org_id)
        db.add(a)
    a.carries_cambridge = carries
    a.cambridge_scale_id = scale_id
    return a


@router.patch("/sections/{section_id}/subjects/{subject_id}", response_model=SubjectAssessmentResponse, dependencies=[_write])
async def set_section_subject(section_id: str, subject_id: str, payload: SubjectAssessmentUpdate,
                              db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Toggle the Cambridge overlay for one subject in a section (upsert)."""
    org_id = current_user.org_id
    await _require_section(db, section_id, org_id)
    subj = (await db.execute(select(Subject).where(Subject.id == subject_id, Subject.org_id == org_id))).scalar_one_or_none()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found.")
    a = await _upsert_assessment(db, org_id, section_id, subject_id, payload.carries_cambridge, payload.cambridge_scale_id)
    await db.flush()
    return SubjectAssessmentResponse(subject_id=subject_id, subject_name=subj.name,
                                     carries_cambridge=a.carries_cambridge, cambridge_scale_id=a.cambridge_scale_id)


@router.post("/sections/{section_id}/subjects/set-cambridge", response_model=list[SubjectAssessmentResponse], dependencies=[_write])
async def set_all_subjects_cambridge(section_id: str, payload: SetCambridgeAllRequest,
                                     db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Apply the Cambridge overlay to EVERY org subject for this section in one call
    ("all subjects carry Cambridge"). Upserts a row per subject."""
    org_id = current_user.org_id
    await _require_section(db, section_id, org_id)
    subjects = (await db.execute(select(Subject).where(Subject.org_id == org_id).order_by(Subject.name))).scalars().all()
    for s in subjects:
        await _upsert_assessment(db, org_id, section_id, s.id, payload.carries_cambridge, payload.cambridge_scale_id)
    await db.flush()
    return [SubjectAssessmentResponse(subject_id=s.id, subject_name=s.name,
                                      carries_cambridge=payload.carries_cambridge, cambridge_scale_id=payload.cambridge_scale_id)
            for s in subjects]


# ── School Reports R3: assessment domains (EYFS / skills / Cambridge strands) ──────

async def _subject_name_map(db, org_id, ids) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(select(Subject.id, Subject.name).where(Subject.org_id == org_id, Subject.id.in_(ids)))).all()
    return {r.id: r.name for r in rows}


def _domain_response(d: AssessmentDomain, subject_name: str | None = None) -> DomainResponse:
    return DomainResponse(
        id=d.id, section_id=d.section_id, domain_type=d.domain_type, name=d.name,
        parent_domain_id=d.parent_domain_id, parent_subject_id=d.parent_subject_id,
        subject_name=subject_name, rating_scale_id=d.rating_scale_id,
        position=d.position, org_id=d.org_id,
    )


async def _require_domain(db, domain_id, org_id) -> AssessmentDomain:
    d = (await db.execute(select(AssessmentDomain).where(
        AssessmentDomain.id == domain_id, AssessmentDomain.org_id == org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Assessment domain not found.")
    return d


async def _validate_domain_refs(db, org_id, section_id, parent_domain_id, parent_subject_id, rating_scale_id):
    """Every FK a domain points at must live in the same org (and, for a parent
    domain, the same section) — never trust a client-supplied id across the tenant."""
    if parent_domain_id:
        p = (await db.execute(select(AssessmentDomain).where(
            AssessmentDomain.id == parent_domain_id, AssessmentDomain.org_id == org_id))).scalar_one_or_none()
        if not p or p.section_id != section_id:
            raise HTTPException(status_code=422, detail="parent_domain_id not found in this section.")
    if parent_subject_id:
        s = (await db.execute(select(Subject).where(
            Subject.id == parent_subject_id, Subject.org_id == org_id))).scalar_one_or_none()
        if not s:
            raise HTTPException(status_code=422, detail="parent_subject_id not found.")
    if rating_scale_id:
        sc = (await db.execute(select(GradingScale).where(
            GradingScale.id == rating_scale_id, GradingScale.org_id == org_id))).scalar_one_or_none()
        if not sc:
            raise HTTPException(status_code=422, detail="rating_scale_id not found.")


@router.get("/sections/{section_id}/domains", response_model=list[DomainResponse], dependencies=[_read])
async def list_domains(section_id: str, domain_type: str | None = Query(default=None),
                       db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """The assessment domains defined for a section (EYFS areas/goals, skills,
    Cambridge strands), ordered for display."""
    org_id = current_user.org_id
    await _require_section(db, section_id, org_id)
    q = select(AssessmentDomain).where(AssessmentDomain.org_id == org_id, AssessmentDomain.section_id == section_id)
    if domain_type:
        q = q.where(AssessmentDomain.domain_type == domain_type)
    domains = (await db.execute(q.order_by(AssessmentDomain.position, AssessmentDomain.name))).scalars().all()
    subj_names = await _subject_name_map(db, org_id, {d.parent_subject_id for d in domains})
    return [_domain_response(d, subj_names.get(d.parent_subject_id)) for d in domains]


@router.post("/sections/{section_id}/domains", response_model=DomainResponse, status_code=201, dependencies=[_write])
async def create_domain(section_id: str, payload: DomainCreate,
                        db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org_id = current_user.org_id
    await _require_section(db, section_id, org_id)
    if payload.domain_type not in DOMAIN_TYPES:
        raise HTTPException(status_code=422, detail="Invalid domain_type.")
    await _validate_domain_refs(db, org_id, section_id, payload.parent_domain_id, payload.parent_subject_id, payload.rating_scale_id)
    d = AssessmentDomain(
        section_id=section_id, domain_type=payload.domain_type, name=payload.name,
        parent_domain_id=payload.parent_domain_id, parent_subject_id=payload.parent_subject_id,
        rating_scale_id=payload.rating_scale_id, position=payload.position, org_id=org_id,
    )
    db.add(d)
    await db.flush()
    subj_names = await _subject_name_map(db, org_id, {d.parent_subject_id})
    return _domain_response(d, subj_names.get(d.parent_subject_id))


@router.patch("/domains/{domain_id}", response_model=DomainResponse, dependencies=[_write])
async def update_domain(domain_id: str, payload: DomainUpdate,
                        db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org_id = current_user.org_id
    d = await _require_domain(db, domain_id, org_id)
    data = payload.model_dump(exclude_unset=True)
    # Re-validate any FK that's being (re)set, against the domain's own section.
    await _validate_domain_refs(
        db, org_id, d.section_id,
        data.get("parent_domain_id", d.parent_domain_id) if "parent_domain_id" in data else None,
        data.get("parent_subject_id", d.parent_subject_id) if "parent_subject_id" in data else None,
        data.get("rating_scale_id", d.rating_scale_id) if "rating_scale_id" in data else None,
    )
    for k, v in data.items():
        setattr(d, k, v)
    await db.flush()
    subj_names = await _subject_name_map(db, org_id, {d.parent_subject_id})
    return _domain_response(d, subj_names.get(d.parent_subject_id))


@router.delete("/domains/{domain_id}", status_code=204, dependencies=[_write])
async def delete_domain(domain_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = await _require_domain(db, domain_id, current_user.org_id)
    await db.delete(d)   # cascades to child goals + any student ratings
    await db.flush()


# Standard taxonomies the seed lays down. All EDITABLE afterwards — a starting
# scaffold, never a locked constant (the school renames/prunes to taste).
_EYFS_AREAS = [
    ("Communication and Language", ["Listening, Attention and Understanding", "Speaking"]),
    ("Physical Development", ["Gross Motor Skills", "Fine Motor Skills"]),
    ("Personal, Social and Emotional Development", ["Self-Regulation", "Managing Self", "Building Relationships"]),
    ("Literacy", ["Comprehension", "Word Reading", "Writing"]),
    ("Mathematics", ["Number", "Numerical Patterns"]),
    ("Understanding the World", ["Past and Present", "People, Culture and Communities", "The Natural World"]),
    ("Expressive Arts and Design", ["Creating with Materials", "Being Imaginative and Expressive"]),
]
_PSYCHOMOTOR = ["Handwriting", "Drawing and Painting", "Sports and Games", "Handling of Tools", "Musical Skills", "Verbal Fluency", "Handling of Laboratory Equipment"]
_AFFECTIVE = ["Punctuality", "Attendance", "Neatness", "Politeness", "Honesty", "Relationship with Others", "Attentiveness in Class", "Self-Control", "Leadership", "Cooperation"]


@router.post("/sections/{section_id}/domains/seed", response_model=list[DomainResponse], dependencies=[_write])
async def seed_domains(section_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Lay down the standard assessment domains for a section, curriculum-aware and
    idempotent (never duplicates an existing name):
      • eyfs → EYFS Areas of Learning + their Early Learning Goals.
      • nigerian/hybrid → psychomotor (skills) + affective (character) domains.
      • hybrid → one Cambridge attainment strand per subject that carries the overlay.
    Everything seeded is editable data; descriptor rating scales are created
    provisional (except EYFS's, a real published framework) so the school confirms
    real labels before a report prints them."""
    org_id = current_user.org_id
    section = await _require_section(db, section_id, org_id)

    # Descriptor rating scales (reuse by name, create bands only when new).
    scales = {s.name.casefold(): s for s in (await db.execute(
        select(GradingScale).where(GradingScale.org_id == org_id))).scalars().all()}

    async def ensure_scale(name, labels, provisional):
        s = scales.get(name.casefold())
        if s:
            return s
        s = GradingScale(name=name, scale_type="descriptor", is_provisional=provisional, org_id=org_id)
        db.add(s)
        await db.flush()
        for i, label in enumerate(labels):
            db.add(GradingBand(scale_id=s.id, grade=label, position=i, org_id=org_id))
        scales[name.casefold()] = s
        return s

    # Existing domains for idempotency: keyed (domain_type, name, parent_domain_id, parent_subject_id).
    existing = (await db.execute(select(AssessmentDomain).where(
        AssessmentDomain.org_id == org_id, AssessmentDomain.section_id == section_id))).scalars().all()
    seen = {(d.domain_type, d.name.casefold(), d.parent_domain_id, d.parent_subject_id) for d in existing}

    def add_domain(domain_type, name, scale, pos, parent_domain_id=None, parent_subject_id=None):
        key = (domain_type, name.casefold(), parent_domain_id, parent_subject_id)
        if key in seen:
            return None
        d = AssessmentDomain(section_id=section_id, domain_type=domain_type, name=name,
                             parent_domain_id=parent_domain_id, parent_subject_id=parent_subject_id,
                             rating_scale_id=scale.id if scale else None, position=pos, org_id=org_id)
        db.add(d)
        seen.add(key)
        return d

    curriculum = (section.curriculum or "nigerian").lower()

    if curriculum == "eyfs":
        eyfs_scale = await ensure_scale("EYFS descriptors", ["Emerging", "Expected", "Exceeding"], provisional=False)
        for ai, (area, goals) in enumerate(_EYFS_AREAS):
            area_dom = add_domain("eyfs_area", area, eyfs_scale, ai)
            if area_dom is None:
                # Area already exists — reuse it as the parent for any missing goals.
                area_dom = next((d for d in existing if d.domain_type == "eyfs_area" and d.name.casefold() == area.casefold()), None)
            if area_dom is not None:
                await db.flush()   # ensure the area has an id before goals reference it
                for gi, goal in enumerate(goals):
                    add_domain("eyfs_goal", goal, eyfs_scale, gi, parent_domain_id=area_dom.id)
    else:
        skill_scale = await ensure_scale("Skills & behaviour (5-point)", ["Excellent", "Very Good", "Good", "Fair", "Poor"], provisional=True)
        for i, name in enumerate(_PSYCHOMOTOR):
            add_domain("psychomotor", name, skill_scale, i)
        for i, name in enumerate(_AFFECTIVE):
            add_domain("affective", name, skill_scale, i)
        if curriculum == "hybrid":
            camb_scale = await ensure_scale("Cambridge attainment", ["Working towards", "Meeting expectations", "Exceeding expectations"], provisional=True)
            # One attainment strand per subject that carries the Cambridge overlay here.
            carried = (await db.execute(select(ReportSubjectAssessment).where(
                ReportSubjectAssessment.org_id == org_id, ReportSubjectAssessment.section_id == section_id,
                ReportSubjectAssessment.carries_cambridge == True,  # noqa: E712
            ))).scalars().all()
            subj_names = await _subject_name_map(db, org_id, {a.subject_id for a in carried})
            for i, a in enumerate(sorted(carried, key=lambda x: (subj_names.get(x.subject_id) or "").lower())):
                sname = subj_names.get(a.subject_id) or "Subject"
                add_domain("cambridge_strand", f"{sname} — Cambridge attainment", camb_scale, i, parent_subject_id=a.subject_id)

    await db.flush()
    domains = (await db.execute(select(AssessmentDomain).where(
        AssessmentDomain.org_id == org_id, AssessmentDomain.section_id == section_id
    ).order_by(AssessmentDomain.position, AssessmentDomain.name))).scalars().all()
    subj_names = await _subject_name_map(db, org_id, {d.parent_subject_id for d in domains})
    return [_domain_response(d, subj_names.get(d.parent_subject_id)) for d in domains]


# ── Academic Weeks (calendar backbone) ────────────────────────────────────────

def _week_dict(w: AcademicWeek) -> WeekResponse:
    return WeekResponse(
        id=w.id, academic_year=w.academic_year, term=w.term, week_number=w.week_number,
        start_date=w.start_date, end_date=w.end_date, label=w.label,
        is_holiday=w.is_holiday, is_locked=w.is_locked, created_at=w.created_at, org_id=w.org_id,
    )


async def _load_week(db: AsyncSession, week_id: str, org_id: str) -> AcademicWeek:
    w = (await db.execute(
        select(AcademicWeek).where(AcademicWeek.id == week_id, AcademicWeek.org_id == org_id)
    )).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Week not found.")
    return w


@router.get("/weeks", response_model=list[WeekResponse], dependencies=[_read])
async def list_weeks(
    academic_year: str | None = Query(default=None),
    term: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(AcademicWeek).where(AcademicWeek.org_id == current_user.org_id)
    if academic_year:
        q = q.where(AcademicWeek.academic_year == academic_year)
    if term:
        q = q.where(AcademicWeek.term == term)
    q = q.order_by(AcademicWeek.academic_year, AcademicWeek.term, AcademicWeek.week_number)
    rows = (await db.execute(q)).scalars().all()
    return [_week_dict(w) for w in rows]


@router.post("/weeks", response_model=WeekResponse, status_code=201, dependencies=[_write])
async def create_week(payload: WeekCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date.")
    w = AcademicWeek(**payload.model_dump(), org_id=current_user.org_id)
    db.add(w)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Week {payload.week_number} already exists for {payload.term} {payload.academic_year}.")
    return _week_dict(w)


@router.post("/weeks/generate", response_model=list[WeekResponse], status_code=201, dependencies=[_write])
async def generate_weeks(payload: WeekGenerate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Fill sequential 7-day weeks across a term's date range. Refuses if the term
    already has weeks, so it never clobbers a calendar an admin has adjusted."""
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date.")
    existing = (await db.execute(
        select(func.count()).select_from(AcademicWeek).where(
            AcademicWeek.org_id == current_user.org_id,
            AcademicWeek.academic_year == payload.academic_year,
            AcademicWeek.term == payload.term,
        )
    )).scalar_one()
    if existing:
        raise HTTPException(status_code=409, detail=f"{payload.term} {payload.academic_year} already has weeks. Delete them first or add weeks manually.")

    created: list[AcademicWeek] = []
    cursor, n = payload.start_date, 1
    while cursor <= payload.end_date and n <= 60:
        w_end = min(cursor + timedelta(days=6), payload.end_date)
        w = AcademicWeek(
            academic_year=payload.academic_year, term=payload.term, week_number=n,
            start_date=cursor, end_date=w_end, org_id=current_user.org_id,
        )
        db.add(w)
        created.append(w)
        cursor += timedelta(days=7)
        n += 1
    await db.flush()
    return [_week_dict(w) for w in created]


@router.patch("/weeks/{week_id}", response_model=WeekResponse, dependencies=[_write])
async def update_week(week_id: str, payload: WeekUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_week(db, week_id, current_user.org_id)
    updates = payload.model_dump(exclude_unset=True)
    # A locked week is frozen except for the act of unlocking it.
    if w.is_locked and set(updates.keys()) - {"is_locked"}:
        raise HTTPException(status_code=409, detail="Week is locked. Unlock it before editing.")
    new_start = updates.get("start_date", w.start_date)
    new_end = updates.get("end_date", w.end_date)
    if new_end < new_start:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date.")
    for k, v in updates.items():
        setattr(w, k, v)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Another week already uses that number for this term.")
    return _week_dict(w)


@router.delete("/weeks/{week_id}", status_code=204, dependencies=[_write])
async def delete_week(week_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_week(db, week_id, current_user.org_id)
    if w.is_locked:
        raise HTTPException(status_code=409, detail="Week is locked. Unlock it before deleting.")
    await db.delete(w)


# ── Custom Fields ────────────────────────────────────────────────────────────────

@router.get("/custom-fields", response_model=list[FieldDefResponse], dependencies=[_read])
async def list_field_defs(entity_type: str | None = Query(default=None), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    base = select(CustomFieldDefinition).where(CustomFieldDefinition.org_id == current_user.org_id, CustomFieldDefinition.is_deleted == False)  # noqa: E712
    if entity_type:
        base = base.where(CustomFieldDefinition.entity_type == entity_type)
    rows = (await db.execute(base.order_by(CustomFieldDefinition.label))).scalars().all()
    return [FieldDefResponse(id=f.id, entity_type=f.entity_type, field_key=f.field_key, label=f.label, field_type=f.field_type, options=f.options, required=f.required, created_at=f.created_at, org_id=f.org_id) for f in rows]


@router.post("/custom-fields", response_model=FieldDefResponse, status_code=201, dependencies=[_write])
async def create_field_def(payload: FieldDefCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    f = CustomFieldDefinition(entity_type=payload.entity_type, field_key=payload.field_key, label=payload.label,
                              field_type=payload.field_type, options=payload.options, required=payload.required, org_id=current_user.org_id)
    db.add(f)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That field key already exists for this entity.")
    return FieldDefResponse(id=f.id, entity_type=f.entity_type, field_key=f.field_key, label=f.label, field_type=f.field_type, options=f.options, required=f.required, created_at=f.created_at, org_id=f.org_id)


@router.delete("/custom-fields/{field_id}", status_code=204, dependencies=[_write])
async def delete_field_def(field_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    f = (await db.execute(select(CustomFieldDefinition).where(CustomFieldDefinition.id == field_id, CustomFieldDefinition.org_id == current_user.org_id, CustomFieldDefinition.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not f:
        raise HTTPException(status_code=404, detail="Field not found.")
    f.is_deleted = True
    f.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.get("/custom-fields/values", response_model=list[FieldValueResponse], dependencies=[_read])
async def list_field_values(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(CustomFieldValue).where(CustomFieldValue.org_id == current_user.org_id, CustomFieldValue.entity_type == entity_type, CustomFieldValue.entity_id == entity_id))).scalars().all()
    return [FieldValueResponse(id=v.id, field_id=v.field_id, entity_type=v.entity_type, entity_id=v.entity_id, value=v.value, org_id=v.org_id) for v in rows]


@router.post("/custom-fields/values", response_model=FieldValueResponse, dependencies=[_write])
async def set_field_value(payload: FieldValueSet, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    fd = (await db.execute(select(CustomFieldDefinition).where(CustomFieldDefinition.id == payload.field_id, CustomFieldDefinition.org_id == current_user.org_id, CustomFieldDefinition.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not fd:
        raise HTTPException(status_code=404, detail="field not found.")
    v = (await db.execute(select(CustomFieldValue).where(CustomFieldValue.org_id == current_user.org_id, CustomFieldValue.field_id == payload.field_id, CustomFieldValue.entity_id == payload.entity_id))).scalar_one_or_none()
    if v:
        v.value = payload.value
    else:
        v = CustomFieldValue(field_id=payload.field_id, entity_type=payload.entity_type, entity_id=payload.entity_id, value=payload.value, org_id=current_user.org_id)
        db.add(v)
    await db.flush()
    return FieldValueResponse(id=v.id, field_id=v.field_id, entity_type=v.entity_type, entity_id=v.entity_id, value=v.value, org_id=v.org_id)


# ── Voting ──────────────────────────────────────────────────────────────────────

async def _poll_response(db, p: Poll, org_id: str, voter_id: str | None) -> PollResponse:
    opts = (await db.execute(select(PollOption).where(PollOption.poll_id == p.id).order_by(PollOption.created_at))).scalars().all()
    counts = dict((oid, c) for oid, c in (await db.execute(
        select(PollVote.option_id, func.count(PollVote.id)).where(PollVote.poll_id == p.id).group_by(PollVote.option_id)
    )).all())
    total = sum(counts.values())
    my = (await db.execute(select(PollVote.option_id).where(PollVote.poll_id == p.id, PollVote.voter_id == voter_id))).scalar_one_or_none() if voter_id else None
    return PollResponse(id=p.id, title=p.title, description=p.description, status=p.status, closes_at=p.closes_at,
                        total_votes=total, options=[PollOptionResult(id=o.id, label=o.label, votes=counts.get(o.id, 0)) for o in opts],
                        my_vote_option_id=my, created_at=p.created_at, org_id=p.org_id)


@router.get("/polls", response_model=PollListResponse, dependencies=[Depends(require_module("school"))])
async def list_polls(status: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
                     db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    base = select(Poll).where(Poll.org_id == current_user.org_id, Poll.is_deleted == False)  # noqa: E712
    if status:
        base = base.where(Poll.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(Poll.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = [await _poll_response(db, p, current_user.org_id, current_user.id) for p in rows]
    return PollListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/polls", response_model=PollResponse, status_code=201, dependencies=[_write])
async def create_poll(payload: PollCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = Poll(title=payload.title, description=payload.description, closes_at=payload.closes_at, status="open", created_by=current_user.id, org_id=current_user.org_id)
    db.add(p)
    await db.flush()
    for label in payload.options:
        db.add(PollOption(poll_id=p.id, label=label, org_id=current_user.org_id))
    await db.flush()
    return await _poll_response(db, p, current_user.org_id, current_user.id)


@router.post("/polls/{poll_id}/close", response_model=PollResponse, dependencies=[_write])
async def close_poll(poll_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(Poll).where(Poll.id == poll_id, Poll.org_id == current_user.org_id, Poll.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Poll not found.")
    p.status = "closed"
    await db.flush()
    return await _poll_response(db, p, current_user.org_id, current_user.id)


@router.delete("/polls/{poll_id}", status_code=204, dependencies=[_write])
async def delete_poll(poll_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(Poll).where(Poll.id == poll_id, Poll.org_id == current_user.org_id, Poll.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Poll not found.")
    p.is_deleted = True
    p.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.post("/polls/{poll_id}/vote", response_model=PollResponse, dependencies=[Depends(require_module("school"))])
async def cast_vote(poll_id: str, payload: CastVote, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Any authenticated member can vote once. Integrity: the unique
    (poll_id, voter_id) constraint makes a second vote a hard 409."""
    p = (await db.execute(select(Poll).where(Poll.id == poll_id, Poll.org_id == current_user.org_id, Poll.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Poll not found.")
    if p.status != "open":
        raise HTTPException(status_code=409, detail="This poll is closed.")
    opt = (await db.execute(select(PollOption).where(PollOption.id == payload.option_id, PollOption.poll_id == p.id))).scalar_one_or_none()
    if not opt:
        raise HTTPException(status_code=404, detail="option not found for this poll.")
    db.add(PollVote(poll_id=p.id, option_id=opt.id, voter_id=current_user.id, org_id=current_user.org_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You have already voted in this poll.")
    return await _poll_response(db, p, current_user.org_id, current_user.id)


# ── Mailbox (announcements) ───────────────────────────────────────────────────────

@router.post("/mailbox/messages", response_model=MessageResponse, status_code=201, dependencies=[_write])
async def send_message(payload: MessageCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    recipients = set(payload.recipient_ids)
    if payload.all_staff:
        staff_ids = (await db.execute(select(User.id).where(User.org_id == current_user.org_id, User.is_deleted == False, User.status == UserStatus.ACTIVE))).scalars().all()  # noqa: E712
        recipients.update(staff_ids)
    recipients.discard(current_user.id)
    if not recipients:
        raise HTTPException(status_code=422, detail="No recipients.")
    m = MailboxMessage(subject=payload.subject, body=payload.body, sender_id=current_user.id,
                       audience="all_staff" if payload.all_staff else "custom", org_id=current_user.org_id)
    db.add(m)
    await db.flush()
    for rid in recipients:
        db.add(MailboxRecipient(message_id=m.id, recipient_id=rid, org_id=current_user.org_id))
    await db.flush()
    return MessageResponse(id=m.id, subject=m.subject, body=m.body, sender_id=m.sender_id, audience=m.audience,
                           recipient_count=len(recipients), read_count=0, created_at=m.created_at, org_id=m.org_id)


@router.get("/mailbox/sent", response_model=list[MessageResponse], dependencies=[_read])
async def list_sent(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(MailboxMessage).where(MailboxMessage.org_id == current_user.org_id, MailboxMessage.sender_id == current_user.id, MailboxMessage.is_deleted == False).order_by(MailboxMessage.created_at.desc()))).scalars().all()  # noqa: E712
    out = []
    for m in rows:
        rc = (await db.execute(select(func.count()).select_from(MailboxRecipient).where(MailboxRecipient.message_id == m.id))).scalar() or 0
        read = (await db.execute(select(func.count()).select_from(MailboxRecipient).where(MailboxRecipient.message_id == m.id, MailboxRecipient.read_at.isnot(None)))).scalar() or 0
        out.append(MessageResponse(id=m.id, subject=m.subject, body=m.body, sender_id=m.sender_id, audience=m.audience, recipient_count=rc, read_count=read, created_at=m.created_at, org_id=m.org_id))
    return out


@router.get("/mailbox/inbox", response_model=list[InboxItemResponse])
async def my_inbox(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(MailboxRecipient, MailboxMessage)
        .join(MailboxMessage, MailboxMessage.id == MailboxRecipient.message_id)
        .where(MailboxRecipient.recipient_id == current_user.id, MailboxRecipient.org_id == current_user.org_id, MailboxMessage.is_deleted == False)  # noqa: E712
        .order_by(MailboxMessage.created_at.desc())
    )).all()
    return [InboxItemResponse(recipient_row_id=r.id, message_id=m.id, subject=m.subject, body=m.body, sender_id=m.sender_id, read_at=r.read_at, created_at=m.created_at) for r, m in rows]


@router.post("/mailbox/inbox/{recipient_row_id}/read", status_code=204)
async def mark_read(recipient_row_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(MailboxRecipient).where(MailboxRecipient.id == recipient_row_id, MailboxRecipient.recipient_id == current_user.id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Inbox item not found.")
    if r.read_at is None:
        r.read_at = datetime.now(timezone.utc)
        await db.flush()


# ── Mobile Manager ───────────────────────────────────────────────────────────────

def _mobile_response(d: MobileDevice) -> MobileDeviceResponse:
    return MobileDeviceResponse(id=d.id, user_id=d.user_id, push_token=d.push_token, platform=d.platform, label=d.label, is_active=d.is_active, last_seen_at=d.last_seen_at, created_at=d.created_at, org_id=d.org_id)


@router.post("/mobile/register", response_model=MobileDeviceResponse, status_code=201)
async def register_mobile(payload: MobileDeviceRegister, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Any authenticated user registers their own device's push token (idempotent on token)."""
    existing = (await db.execute(select(MobileDevice).where(MobileDevice.org_id == current_user.org_id, MobileDevice.push_token == payload.push_token))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.user_id = current_user.id
        existing.platform = payload.platform or existing.platform
        existing.label = payload.label or existing.label
        existing.is_active = True
        existing.last_seen_at = now
        await db.flush()
        return _mobile_response(existing)
    d = MobileDevice(user_id=current_user.id, push_token=payload.push_token, platform=payload.platform, label=payload.label, is_active=True, last_seen_at=now, org_id=current_user.org_id)
    db.add(d)
    await db.flush()
    return _mobile_response(d)


@router.get("/mobile/devices", response_model=list[MobileDeviceResponse], dependencies=[_read])
async def list_mobile_devices(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(MobileDevice).where(MobileDevice.org_id == current_user.org_id).order_by(MobileDevice.created_at.desc()))).scalars().all()
    return [_mobile_response(d) for d in rows]


@router.delete("/mobile/devices/{device_id}", status_code=204, dependencies=[_write])
async def delete_mobile_device(device_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = (await db.execute(select(MobileDevice).where(MobileDevice.id == device_id, MobileDevice.org_id == current_user.org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found.")
    await db.delete(d)


@router.get("/mobile/config", response_model=list[AppConfigResponse])
async def get_app_config(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Authenticated read — the mobile app fetches its config toggles."""
    rows = (await db.execute(select(MobileAppConfig).where(MobileAppConfig.org_id == current_user.org_id).order_by(MobileAppConfig.key))).scalars().all()
    return [AppConfigResponse(id=c.id, key=c.key, value=c.value, description=c.description, org_id=c.org_id) for c in rows]


@router.post("/mobile/config", response_model=AppConfigResponse, dependencies=[_write])
async def set_app_config(payload: AppConfigSet, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(MobileAppConfig).where(MobileAppConfig.org_id == current_user.org_id, MobileAppConfig.key == payload.key))).scalar_one_or_none()
    if c:
        c.value = payload.value
        c.description = payload.description if payload.description is not None else c.description
    else:
        c = MobileAppConfig(key=payload.key, value=payload.value, description=payload.description, org_id=current_user.org_id)
        db.add(c)
    await db.flush()
    return AppConfigResponse(id=c.id, key=c.key, value=c.value, description=c.description, org_id=c.org_id)
