"""Administration & Platform router (Batch 7), prefix ``/platform``.

School Setup, Custom Fields, Voting, Mailbox (announcements), Mobile Manager.
Admin config is ``settings:*``; per-user surfaces (mailbox inbox, registering a
mobile device, reading app config) are authenticated-only so end users can use
them. Voting integrity: one vote per (poll, voter) is DB-enforced and results
are derived from votes, never a mutable tally.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_module
from app.core.permissions import AnyPermissionChecker, PermissionChecker
from app.models.user import User, UserStatus
from app.models.modules.platform import (
    AcademicSession, AcademicWeek, SchoolHouse, GradingBand,
    SchoolSection, GradingScale, ReportTemplate, ReportSubjectAssessment,
    AssessmentDomain,
    AcademicTerm, AcademicSubTerm, TermPeriod, ReportDeadline,
    ReportCommentType, ResultDefaultComment, ReportBranding,
    ReportLevelSetting, ReportSubjectExclusion,
    AssessmentGroup, Assessment, Cumulative, CumulativeComponent, StudentAssessmentScore,
    StudentReportComment, ClassPcTeacher,
    CustomFieldDefinition, CustomFieldValue,
    Poll, PollOption, PollVote,
    MailboxMessage, MailboxRecipient,
    MobileDevice, MobileAppConfig,
)
from app.models.modules.school import SchoolClass, Subject, Student, StudentReport, Timetable
from app.schemas.platform import (
    SessionCreate, SessionUpdate, SessionResponse, CurrentSessionResponse,
    HouseCreate, HouseUpdate, HouseResponse, BandCreate, BandResponse,
    WeekCreate, WeekUpdate, WeekGenerate, WeekResponse,
    FieldDefCreate, FieldDefResponse, FieldValueSet, FieldValueResponse,
    PollCreate, PollResponse, PollOptionResult, PollListResponse, CastVote,
    MessageCreate, MessageResponse, InboxItemResponse,
    MobileDeviceRegister, MobileDeviceResponse, AppConfigSet, AppConfigResponse,
    SectionCreate, SectionUpdate, SectionResponse,
    GradingScaleCreate, GradingScaleResponse, GradingScaleUpdate, ScaleBandCreate,
    SCALE_PURPOSES, BrandingUpdate, BrandingResponse,
    RESULT_TYPES, LevelSettingUpsert, LevelSettingResponse,
    SubjectExclusionCreate, SubjectExclusionResponse,
    AssessmentGroupCreate, AssessmentGroupUpdate, AssessmentGroupResponse,
    AssessmentCreate, AssessmentUpdate, AssessmentResponse,
    CUMUL_TYPES, REF_TYPES, CumulComponentIn, CumulComponentOut,
    CumulativeCreate, CumulativeUpdate, CumulativeResponse,
    ReportEntryGrid, ReportEntryAssessment, ReportEntryStudent, ScoreItem, ReportEntrySave, TeachingAssignment,
    BroadsheetResponse, BroadsheetRow, BroadsheetCell, BroadsheetSubject, BroadsheetBand,
    CardColumn, CardSubjectRow, ReportCardResponse,
    REPORT_COMMENT_KINDS, CommentGridRow, CommentGridResponse, CommentItem, CommentGridSave,
    InsightResponse, InsightSubject, InsightGender, InsightClass,
    ScoreUploadResult,
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateResponse, AutoMapResult,
    SubjectAssessmentResponse, SubjectAssessmentUpdate, SetCambridgeAllRequest,
    DomainCreate, DomainUpdate, DomainResponse, DOMAIN_TYPES,
    SECTION_CURRICULA, ASSESSMENT_MODES, SCALE_TYPES,
    SubTermCreate, SubTermUpdate, SubTermResponse,
    TermCreate, TermUpdate, TermResponse,
    TermPeriodUpsert, TermPeriodResponse, DeadlineUpsert, DeadlineResponse,
    CommentTypeCreate, CommentTypeUpdate, CommentTypeResponse,
    DefaultCommentCreate, DefaultCommentUpdate, DefaultCommentResponse,
    COMMENT_LENGTH_TYPES, TEACHER_TYPES,
)
from app.services.ledger import money  # Decimal helper for grading bands
from app.services.report_engine import evaluate_cumulative, round_dp
from app.services.import_files import rows_from_upload

router = APIRouter(prefix="/platform", tags=["Administration & Platform"], dependencies=[Depends(require_module("school"))])

_read = Depends(PermissionChecker("settings:read"))
_write = Depends(PermissionChecker("settings:write"))
# The current-session resolver + report CONFIG reads are consumed by term-aware
# features (exam/grade/CBT forms) and by every teacher-facing report page, so they
# ride a staff-read tier rather than the admin settings scope. AnyPermission:
# `school:reports:read` keeps them reachable for the classroom tier, which no
# longer holds the broad `school:read` (see role.py — that grant reached every
# fine-grained child). Widening only; no role loses access.
_school_read = Depends(AnyPermissionChecker("school:read", "school:reports:read"))
# Report Entry is grade entry, not admin config — gate it on the reports scope.
_reports_write = Depends(PermissionChecker("school:reports:write"))
# Admin-only report actions (Approve/Process, Reports Upload) — the classroom tier
# holds school:reports:write but NOT school_admin, so this excludes them.
_report_admin_write = Depends(PermissionChecker("school_admin:write"))


def _report_admin(user: User) -> bool:
    """A report ADMIN (org_admin / manager / principal / head / super) — bypasses
    the class-teacher / subject-teacher scoping that constrains ordinary teachers.
    Teachers hold school:write (not school_admin) so this is False for them."""
    return user.has_permission("school_admin:read")


async def _teacher_assignments(db: AsyncSession, org_id: str, user_id: str) -> set[tuple[str, str]]:
    """The (class_id, subject_id) pairs a teacher actually teaches — from the
    Timetable (the real per-class-per-subject assignment)."""
    rows = (await db.execute(select(Timetable.class_id, Timetable.subject_id).where(
        Timetable.org_id == org_id, Timetable.teacher_id == user_id))).all()
    return {(r.class_id, r.subject_id) for r in rows}


async def _class_teacher_id(db: AsyncSession, org_id: str, class_id: str) -> str | None:
    return (await db.execute(select(SchoolClass.teacher_id).where(
        SchoolClass.id == class_id, SchoolClass.org_id == org_id))).scalar_one_or_none()


async def _pc_teacher_id(db: AsyncSession, org_id: str, class_id: str) -> str | None:
    """The class's PC teacher — the ClassPcTeacher lookup, else the class/form
    teacher (today's default). Data-driven, reassignable later."""
    pc = (await db.execute(select(ClassPcTeacher.teacher_id).where(
        ClassPcTeacher.org_id == org_id, ClassPcTeacher.class_id == class_id))).scalar_one_or_none()
    return pc or await _class_teacher_id(db, org_id, class_id)


async def _gate_comment_access(db: AsyncSession, org_id: str, user: User, class_id: str | None, kind: str):
    """Report-card comment access: admins pass. Otherwise the School Head comment
    (kind=head) is admin-only, and the PC Teacher comment (kind=pc) is limited to
    the class's PC teacher."""
    if _report_admin(user):
        return
    if kind == "head":
        raise HTTPException(status_code=403, detail="Only an administrator can enter the school head's comment.")
    if not class_id or await _pc_teacher_id(db, org_id, class_id) != user.id:
        raise HTTPException(status_code=403, detail="You are not the PC teacher for this class.")


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


async def _house_section_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(select(SchoolSection.id, SchoolSection.name).where(SchoolSection.org_id == org_id, SchoolSection.id.in_(ids)))).all()
    return {r.id: r.name for r in rows}


def _house_response(h: SchoolHouse, section_name: str | None = None) -> HouseResponse:
    return HouseResponse(
        id=h.id, name=h.name, color=h.color, motto=h.motto,
        section_id=getattr(h, "section_id", None), section_name=section_name,
        is_active=bool(getattr(h, "is_active", True)), created_at=h.created_at, org_id=h.org_id,
    )


@router.get("/houses", response_model=list[HouseResponse], dependencies=[_read])
async def list_houses(section: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(SchoolHouse).where(SchoolHouse.org_id == current_user.org_id)
    if section:
        q = q.where(SchoolHouse.section_id == section)
    rows = (await db.execute(q.order_by(SchoolHouse.name))).scalars().all()
    names = await _house_section_names(db, current_user.org_id, {h.section_id for h in rows})
    return [_house_response(h, names.get(h.section_id)) for h in rows]


@router.post("/houses", response_model=HouseResponse, status_code=201, dependencies=[_write])
async def create_house(payload: HouseCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    h = SchoolHouse(**payload.model_dump(exclude_none=True), org_id=current_user.org_id)
    db.add(h)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A house with that name already exists.")
    names = await _house_section_names(db, current_user.org_id, {h.section_id})
    return _house_response(h, names.get(h.section_id))


@router.patch("/houses/{house_id}", response_model=HouseResponse, dependencies=[_write])
async def update_house(house_id: str, payload: HouseUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    h = (await db.execute(select(SchoolHouse).where(SchoolHouse.id == house_id, SchoolHouse.org_id == current_user.org_id))).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="House not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(h, f, v)
    await db.flush()
    names = await _house_section_names(db, current_user.org_id, {h.section_id})
    return _house_response(h, names.get(h.section_id))


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
        show_in_table=scale.show_in_table, purpose=scale.purpose,
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
    if payload.purpose not in SCALE_PURPOSES:
        raise HTTPException(status_code=422, detail=f"purpose must be one of {sorted(SCALE_PURPOSES)}")
    scale = GradingScale(name=payload.name.strip(), scale_type=payload.scale_type, is_provisional=payload.is_provisional,
                         show_in_table=payload.show_in_table, purpose=payload.purpose, org_id=current_user.org_id)
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


@router.patch("/grading-scales/{scale_id}", response_model=GradingScaleResponse, dependencies=[_write])
async def update_scale(scale_id: str, payload: GradingScaleUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Rename a scale or set its report role (Grading System tab): show_in_table +
    purpose (grade|keys|cumulative|mock)."""
    scale = (await db.execute(select(GradingScale).where(GradingScale.id == scale_id, GradingScale.org_id == current_user.org_id))).scalar_one_or_none()
    if not scale:
        raise HTTPException(status_code=404, detail="Scale not found.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("purpose") and data["purpose"] not in SCALE_PURPOSES:
        raise HTTPException(status_code=422, detail=f"purpose must be one of {sorted(SCALE_PURPOSES)}")
    for f, v in data.items():
        setattr(scale, f, v)
    await db.flush()
    bands = (await db.execute(select(GradingBand).where(GradingBand.scale_id == scale_id, GradingBand.org_id == current_user.org_id))).scalars().all()
    return _scale_response(scale, bands)


@router.delete("/grading-scales/{scale_id}", status_code=204, dependencies=[_write])
async def delete_scale(scale_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    scale = (await db.execute(select(GradingScale).where(GradingScale.id == scale_id, GradingScale.org_id == current_user.org_id))).scalar_one_or_none()
    if not scale:
        raise HTTPException(status_code=404, detail="Scale not found.")
    await db.delete(scale)   # bands CASCADE; templates.grading_scale_id → SET NULL


# ── Secondary Report S-1b: School Motto, Seal & Sponsor (report branding) ────

def _branding_response(b: ReportBranding | None) -> BrandingResponse:
    if not b:
        return BrandingResponse()
    return BrandingResponse(
        id=b.id, school_motto=b.school_motto, school_name_alias=b.school_name_alias,
        school_address=b.school_address, school_website=b.school_website, school_email=b.school_email,
        school_phone=b.school_phone, class_teacher_title=b.class_teacher_title,
        school_head_title=b.school_head_title, school_head_name=b.school_head_name,
        full_term_passmark=b.full_term_passmark, mid_term_passmark=b.mid_term_passmark,
        min_average_honours=b.min_average_honours, promotion_comment=b.promotion_comment,
        demotion_comment=b.demotion_comment, logo_url=b.logo_url, head_signature_url=b.head_signature_url,
        logo_background_url=b.logo_background_url, sponsor_url=b.sponsor_url,
    )


@router.get("/report-branding", response_model=BrandingResponse, dependencies=[_school_read])
async def get_report_branding(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    b = (await db.execute(select(ReportBranding).where(ReportBranding.org_id == current_user.org_id))).scalar_one_or_none()
    return _branding_response(b)


@router.put("/report-branding", response_model=BrandingResponse, dependencies=[_write])
async def update_report_branding(payload: BrandingUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    b = (await db.execute(select(ReportBranding).where(ReportBranding.org_id == current_user.org_id))).scalar_one_or_none()
    if not b:
        b = ReportBranding(org_id=current_user.org_id)
        db.add(b)
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(b, f, v)
    await db.flush()
    return _branding_response(b)


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
    """One-click setup: create/refresh the Early Years / Primary / Secondary
    sections (British curriculum: Year 1–6 Primary, Year 7–12 Secondary) with their
    level aliases, the school's REAL grading scale + bands, and a template per
    section. Idempotent + self-healing: re-running updates templates in place, so an
    earlier provisional seed is replaced by the confirmed constants (one shared A–F
    scale; CA/exam 40/60 for Primary + Secondary; EYFS descriptors for Early Years)."""
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

    # "Early Years" is the EYFS section (aliases still include NURSERY etc. so
    # existing class levels auto-map). EYFS detection keys on curriculum, not name.
    early_years = ensure_section("Early Years", "eyfs", 0, ["PLAY GROUP", "PRE-NURSERY", "NURSERY", "EARLY YEARS", "RECEPTION"])
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

    ensure_template(early_years, "Early Years (EYFS)", "descriptive", None, None, None)
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


# ── Secondary Report S-0: Terms & Sub-term ───────────────────────────────────

def _subterm_response(s: AcademicSubTerm) -> SubTermResponse:
    return SubTermResponse(id=s.id, name=s.name, alias=s.alias, position=s.position, is_active=s.is_active)


@router.get("/academic-sub-terms", response_model=list[SubTermResponse], dependencies=[_school_read])
async def list_sub_terms(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.org_id == current_user.org_id)
                             .order_by(AcademicSubTerm.position, AcademicSubTerm.name))).scalars().all()
    return [_subterm_response(s) for s in rows]


@router.post("/academic-sub-terms", response_model=SubTermResponse, status_code=201, dependencies=[_write])
async def create_sub_term(payload: SubTermCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    dupe = (await db.execute(select(AcademicSubTerm.id).where(
        AcademicSubTerm.org_id == current_user.org_id, func.lower(AcademicSubTerm.name) == payload.name.lower()))).scalar_one_or_none()
    if dupe:
        raise HTTPException(status_code=409, detail="A sub-term with that name already exists.")
    s = AcademicSubTerm(org_id=current_user.org_id, **payload.model_dump())
    db.add(s)
    await db.flush()
    return _subterm_response(s)


@router.patch("/academic-sub-terms/{sub_term_id}", response_model=SubTermResponse, dependencies=[_write])
async def update_sub_term(sub_term_id: str, payload: SubTermUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.id == sub_term_id, AcademicSubTerm.org_id == current_user.org_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Sub-term not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, f, v)
    await db.flush()
    return _subterm_response(s)


@router.delete("/academic-sub-terms/{sub_term_id}", status_code=204, dependencies=[_write])
async def delete_sub_term(sub_term_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.id == sub_term_id, AcademicSubTerm.org_id == current_user.org_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Sub-term not found.")
    await db.delete(s)


async def _term_response(db: AsyncSession, org_id: str, t: AcademicTerm, sub_names: dict) -> TermResponse:
    st = sub_names.get(t.active_sub_term_id) if t.active_sub_term_id else None
    return TermResponse(id=t.id, name=t.name, alias=t.alias, position=t.position, is_active=t.is_active,
                        active_sub_term_id=t.active_sub_term_id,
                        active_sub_term_name=(st[0] if st else None),
                        active_sub_term_position=(st[1] if st else None))


@router.get("/academic-terms", response_model=list[TermResponse], dependencies=[_school_read])
async def list_terms(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == current_user.org_id)
                             .order_by(AcademicTerm.position, AcademicTerm.name))).scalars().all()
    subs = {s.id: (s.name, s.position) for s in (await db.execute(
        select(AcademicSubTerm).where(AcademicSubTerm.org_id == current_user.org_id))).scalars().all()}
    return [await _term_response(db, current_user.org_id, t, subs) for t in rows]


async def _validate_sub_term(db: AsyncSession, org_id: str, sub_term_id: str | None):
    if sub_term_id is None:
        return
    ok = (await db.execute(select(AcademicSubTerm.id).where(
        AcademicSubTerm.id == sub_term_id, AcademicSubTerm.org_id == org_id))).scalar_one_or_none()
    if not ok:
        raise HTTPException(status_code=422, detail="active_sub_term_id: not a sub-term in your organisation")


async def _deactivate_other_terms(db: AsyncSession, org_id: str, keep_id: str | None):
    await db.execute(update(AcademicTerm).where(
        AcademicTerm.org_id == org_id, AcademicTerm.id != (keep_id or "")).values(is_active=False))


@router.post("/academic-terms", response_model=TermResponse, status_code=201, dependencies=[_write])
async def create_term(payload: TermCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    dupe = (await db.execute(select(AcademicTerm.id).where(
        AcademicTerm.org_id == current_user.org_id, func.lower(AcademicTerm.name) == payload.name.lower()))).scalar_one_or_none()
    if dupe:
        raise HTTPException(status_code=409, detail="A term with that name already exists.")
    t = AcademicTerm(org_id=current_user.org_id, **payload.model_dump())
    db.add(t)
    await db.flush()
    subs = {s.id: (s.name, s.position) for s in (await db.execute(
        select(AcademicSubTerm).where(AcademicSubTerm.org_id == current_user.org_id))).scalars().all()}
    return await _term_response(db, current_user.org_id, t, subs)


@router.patch("/academic-terms/{term_id}", response_model=TermResponse, dependencies=[_write])
async def update_term(term_id: str, payload: TermUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = (await db.execute(select(AcademicTerm).where(AcademicTerm.id == term_id, AcademicTerm.org_id == current_user.org_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Term not found.")
    data = payload.model_dump(exclude_unset=True)
    if "active_sub_term_id" in data:
        await _validate_sub_term(db, current_user.org_id, data["active_sub_term_id"])
    for f, v in data.items():
        setattr(t, f, v)
    await db.flush()
    # Exactly one active term: if this one just became active, deactivate the rest.
    if data.get("is_active") is True:
        await _deactivate_other_terms(db, current_user.org_id, t.id)
    subs = {s.id: (s.name, s.position) for s in (await db.execute(
        select(AcademicSubTerm).where(AcademicSubTerm.org_id == current_user.org_id))).scalars().all()}
    return await _term_response(db, current_user.org_id, t, subs)


@router.delete("/academic-terms/{term_id}", status_code=204, dependencies=[_write])
async def delete_term(term_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = (await db.execute(select(AcademicTerm).where(AcademicTerm.id == term_id, AcademicTerm.org_id == current_user.org_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Term not found.")
    await db.delete(t)


@router.post("/academic-terms/bootstrap", response_model=list[TermResponse], dependencies=[_write])
async def bootstrap_terms(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Idempotent seed of the standard terms (Autumn/Spring/Summer) + sub-terms
    (Half-Term/Full-Term). Only adds what's missing; never duplicates."""
    org = current_user.org_id
    have_subs = {s.name.lower() for s in (await db.execute(
        select(AcademicSubTerm).where(AcademicSubTerm.org_id == org))).scalars().all()}
    for pos, name in enumerate([("Half-Term"), ("Full-Term")], start=1):
        if name.lower() not in have_subs:
            db.add(AcademicSubTerm(org_id=org, name=name, position=pos, is_active=True))
    have_terms = {t.name.lower() for t in (await db.execute(
        select(AcademicTerm).where(AcademicTerm.org_id == org))).scalars().all()}
    for pos, name in enumerate(["Autumn", "Spring", "Summer"], start=1):
        if name.lower() not in have_terms:
            db.add(AcademicTerm(org_id=org, name=name, position=pos, is_active=False))
    await db.flush()
    return await list_terms(db=db, current_user=current_user)


# ── S-0: Term periods (Term Begins/Ends + Attendance Setup) ──────────────────

async def _term_sub_names(db: AsyncSession, org_id: str):
    tnames = {t.id: t.name for t in (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == org_id))).scalars().all()}
    snames = {s.id: s.name for s in (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.org_id == org_id))).scalars().all()}
    return tnames, snames


def _period_response(p: TermPeriod, tnames, snames) -> TermPeriodResponse:
    return TermPeriodResponse(
        id=p.id, session_id=p.session_id, term_id=p.term_id, term_name=tnames.get(p.term_id),
        sub_term_id=p.sub_term_id, sub_term_name=snames.get(p.sub_term_id),
        begin_date=p.begin_date, end_date=p.end_date, next_term_begins=p.next_term_begins,
        published_date=p.published_date, excluded_days=p.excluded_days, total_days=p.total_days)


@router.get("/term-periods", response_model=list[TermPeriodResponse], dependencies=[_school_read])
async def list_term_periods(session_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(TermPeriod).where(TermPeriod.org_id == current_user.org_id)
    if session_id:
        q = q.where(TermPeriod.session_id == session_id)
    rows = (await db.execute(q)).scalars().all()
    tnames, snames = await _term_sub_names(db, current_user.org_id)
    rows = sorted(rows, key=lambda p: (snames.get(p.sub_term_id) or "", tnames.get(p.term_id) or ""))
    return [_period_response(p, tnames, snames) for p in rows]


@router.post("/term-periods", response_model=TermPeriodResponse, status_code=201, dependencies=[_write])
async def upsert_term_period(payload: TermPeriodUpsert, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Create or update the dates/attendance for a (session, term, sub-term)."""
    org = current_user.org_id
    existing = (await db.execute(select(TermPeriod).where(
        TermPeriod.org_id == org, TermPeriod.session_id == payload.session_id,
        TermPeriod.term_id == payload.term_id, TermPeriod.sub_term_id == payload.sub_term_id))).scalar_one_or_none()
    data = payload.model_dump()
    if existing:
        for f, v in data.items():
            setattr(existing, f, v)
        p = existing
    else:
        p = TermPeriod(org_id=org, **data)
        db.add(p)
    await db.flush()
    tnames, snames = await _term_sub_names(db, org)
    return _period_response(p, tnames, snames)


@router.patch("/term-periods/{period_id}", response_model=TermPeriodResponse, dependencies=[_write])
async def update_term_period(period_id: str, payload: TermPeriodUpsert, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(TermPeriod).where(TermPeriod.id == period_id, TermPeriod.org_id == current_user.org_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Term period not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, f, v)
    await db.flush()
    tnames, snames = await _term_sub_names(db, current_user.org_id)
    return _period_response(p, tnames, snames)


@router.delete("/term-periods/{period_id}", status_code=204, dependencies=[_write])
async def delete_term_period(period_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(TermPeriod).where(TermPeriod.id == period_id, TermPeriod.org_id == current_user.org_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Term period not found.")
    await db.delete(p)


# ── S-0: Deadlines ───────────────────────────────────────────────────────────

def _deadline_response(d: ReportDeadline, tnames, snames) -> DeadlineResponse:
    return DeadlineResponse(id=d.id, session_id=d.session_id, term_id=d.term_id, term_name=tnames.get(d.term_id),
                            sub_term_id=d.sub_term_id, sub_term_name=(snames.get(d.sub_term_id) if d.sub_term_id else None),
                            status=d.status, submission_deadline=d.submission_deadline)


@router.get("/report-deadlines", response_model=list[DeadlineResponse], dependencies=[_school_read])
async def list_deadlines(session_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(ReportDeadline).where(ReportDeadline.org_id == current_user.org_id)
    if session_id:
        q = q.where(ReportDeadline.session_id == session_id)
    rows = (await db.execute(q.order_by(ReportDeadline.created_at))).scalars().all()
    tnames, snames = await _term_sub_names(db, current_user.org_id)
    return [_deadline_response(d, tnames, snames) for d in rows]


@router.post("/report-deadlines", response_model=DeadlineResponse, status_code=201, dependencies=[_write])
async def create_deadline(payload: DeadlineUpsert, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = ReportDeadline(org_id=current_user.org_id, **payload.model_dump())
    db.add(d)
    await db.flush()
    tnames, snames = await _term_sub_names(db, current_user.org_id)
    return _deadline_response(d, tnames, snames)


@router.patch("/report-deadlines/{deadline_id}", response_model=DeadlineResponse, dependencies=[_write])
async def update_deadline(deadline_id: str, payload: DeadlineUpsert, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = (await db.execute(select(ReportDeadline).where(ReportDeadline.id == deadline_id, ReportDeadline.org_id == current_user.org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Deadline not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(d, f, v)
    await db.flush()
    tnames, snames = await _term_sub_names(db, current_user.org_id)
    return _deadline_response(d, tnames, snames)


@router.delete("/report-deadlines/{deadline_id}", status_code=204, dependencies=[_write])
async def delete_deadline(deadline_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = (await db.execute(select(ReportDeadline).where(ReportDeadline.id == deadline_id, ReportDeadline.org_id == current_user.org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Deadline not found.")
    await db.delete(d)


# ── Secondary Report S-1a: Comment types ─────────────────────────────────────

def _comment_type_response(c: ReportCommentType) -> CommentTypeResponse:
    return CommentTypeResponse(id=c.id, name=c.name, comment_type=c.comment_type,
                              max_length=c.max_length, is_active=c.is_active)


@router.get("/report-comment-types", response_model=list[CommentTypeResponse], dependencies=[_school_read])
async def list_comment_types(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(ReportCommentType).where(ReportCommentType.org_id == current_user.org_id)
                             .order_by(ReportCommentType.created_at))).scalars().all()
    return [_comment_type_response(c) for c in rows]


@router.post("/report-comment-types", response_model=CommentTypeResponse, status_code=201, dependencies=[_write])
async def create_comment_type(payload: CommentTypeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.comment_type not in COMMENT_LENGTH_TYPES:
        raise HTTPException(status_code=422, detail=f"comment_type must be one of {sorted(COMMENT_LENGTH_TYPES)}")
    dupe = (await db.execute(select(ReportCommentType.id).where(
        ReportCommentType.org_id == current_user.org_id, func.lower(ReportCommentType.name) == payload.name.lower()))).scalar_one_or_none()
    if dupe:
        raise HTTPException(status_code=409, detail="A comment type with that name already exists.")
    c = ReportCommentType(org_id=current_user.org_id, **payload.model_dump())
    db.add(c)
    await db.flush()
    return _comment_type_response(c)


@router.patch("/report-comment-types/{type_id}", response_model=CommentTypeResponse, dependencies=[_write])
async def update_comment_type(type_id: str, payload: CommentTypeUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(ReportCommentType).where(ReportCommentType.id == type_id, ReportCommentType.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Comment type not found.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("comment_type") and data["comment_type"] not in COMMENT_LENGTH_TYPES:
        raise HTTPException(status_code=422, detail=f"comment_type must be one of {sorted(COMMENT_LENGTH_TYPES)}")
    for f, v in data.items():
        setattr(c, f, v)
    await db.flush()
    return _comment_type_response(c)


@router.delete("/report-comment-types/{type_id}", status_code=204, dependencies=[_write])
async def delete_comment_type(type_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(ReportCommentType).where(ReportCommentType.id == type_id, ReportCommentType.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Comment type not found.")
    await db.delete(c)


# ── S-1a: Result Default Comments ────────────────────────────────────────────

def _default_comment_response(d: ResultDefaultComment, scale_names: dict) -> DefaultCommentResponse:
    return DefaultCommentResponse(
        id=d.id, teacher_type=d.teacher_type, grading_scale_id=d.grading_scale_id,
        grading_scale_name=(scale_names.get(d.grading_scale_id) if d.grading_scale_id else None),
        year_group=d.year_group, min_score=d.min_score, max_score=d.max_score, comment=d.comment)


@router.get("/result-default-comments", response_model=list[DefaultCommentResponse], dependencies=[_school_read])
async def list_default_comments(teacher_type: str | None = None, grading_scale_id: str | None = None,
                                year_group: str | None = None, db: AsyncSession = Depends(get_db),
                                current_user: User = Depends(get_current_active_user)):
    q = select(ResultDefaultComment).where(ResultDefaultComment.org_id == current_user.org_id)
    if teacher_type:
        q = q.where(ResultDefaultComment.teacher_type == teacher_type)
    if grading_scale_id:
        q = q.where(ResultDefaultComment.grading_scale_id == grading_scale_id)
    if year_group:
        q = q.where(ResultDefaultComment.year_group == year_group)
    rows = (await db.execute(q.order_by(ResultDefaultComment.max_score.desc().nullslast()))).scalars().all()
    scale_names = {s.id: s.name for s in (await db.execute(
        select(GradingScale).where(GradingScale.org_id == current_user.org_id))).scalars().all()}
    return [_default_comment_response(d, scale_names) for d in rows]


@router.post("/result-default-comments", response_model=DefaultCommentResponse, status_code=201, dependencies=[_write])
async def create_default_comment(payload: DefaultCommentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.teacher_type not in TEACHER_TYPES:
        raise HTTPException(status_code=422, detail=f"teacher_type must be one of {sorted(TEACHER_TYPES)}")
    if payload.grading_scale_id:
        ok = (await db.execute(select(GradingScale.id).where(
            GradingScale.id == payload.grading_scale_id, GradingScale.org_id == current_user.org_id))).scalar_one_or_none()
        if not ok:
            raise HTTPException(status_code=422, detail="grading_scale_id: not a scale in your organisation")
    d = ResultDefaultComment(org_id=current_user.org_id, **payload.model_dump())
    db.add(d)
    await db.flush()
    scale_names = {s.id: s.name for s in (await db.execute(
        select(GradingScale).where(GradingScale.org_id == current_user.org_id))).scalars().all()}
    return _default_comment_response(d, scale_names)


@router.patch("/result-default-comments/{comment_id}", response_model=DefaultCommentResponse, dependencies=[_write])
async def update_default_comment(comment_id: str, payload: DefaultCommentUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = (await db.execute(select(ResultDefaultComment).where(ResultDefaultComment.id == comment_id, ResultDefaultComment.org_id == current_user.org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Default comment not found.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("teacher_type") and data["teacher_type"] not in TEACHER_TYPES:
        raise HTTPException(status_code=422, detail=f"teacher_type must be one of {sorted(TEACHER_TYPES)}")
    for f, v in data.items():
        setattr(d, f, v)
    await db.flush()
    scale_names = {s.id: s.name for s in (await db.execute(
        select(GradingScale).where(GradingScale.org_id == current_user.org_id))).scalars().all()}
    return _default_comment_response(d, scale_names)


@router.delete("/result-default-comments/{comment_id}", status_code=204, dependencies=[_write])
async def delete_default_comment(comment_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = (await db.execute(select(ResultDefaultComment).where(ResultDefaultComment.id == comment_id, ResultDefaultComment.org_id == current_user.org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Default comment not found.")
    await db.delete(d)


# ── Secondary Report S-1c: Result Type + Result Photo (per year-group) ───────

def _level_setting_response(s: ReportLevelSetting) -> LevelSettingResponse:
    return LevelSettingResponse(id=s.id, year_group=s.year_group, result_type=s.result_type,
                                show_position=s.show_position, show_photo=s.show_photo)


@router.get("/report-level-settings", response_model=list[LevelSettingResponse], dependencies=[_school_read])
async def list_level_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(ReportLevelSetting).where(ReportLevelSetting.org_id == current_user.org_id)
                             .order_by(ReportLevelSetting.year_group))).scalars().all()
    return [_level_setting_response(s) for s in rows]


@router.put("/report-level-settings", response_model=LevelSettingResponse, dependencies=[_write])
async def upsert_level_setting(payload: LevelSettingUpsert, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Set a year-group's report options (Result Type + Result Photo tabs). Upserts
    the single row per (org, year_group)."""
    if payload.result_type not in RESULT_TYPES:
        raise HTTPException(status_code=422, detail=f"result_type must be one of {sorted(RESULT_TYPES)}")
    s = (await db.execute(select(ReportLevelSetting).where(
        ReportLevelSetting.org_id == current_user.org_id, ReportLevelSetting.year_group == payload.year_group))).scalar_one_or_none()
    if not s:
        s = ReportLevelSetting(org_id=current_user.org_id, year_group=payload.year_group)
        db.add(s)
    s.result_type = payload.result_type
    s.show_position = payload.show_position
    s.show_photo = payload.show_photo
    await db.flush()
    return _level_setting_response(s)


# ── S-1c: Subjects For Score Exclusion (per year-group) ──────────────────────

@router.get("/report-subject-exclusions", response_model=list[SubjectExclusionResponse], dependencies=[_school_read])
async def list_subject_exclusions(year_group: str | None = None, db: AsyncSession = Depends(get_db),
                                  current_user: User = Depends(get_current_active_user)):
    q = select(ReportSubjectExclusion).where(ReportSubjectExclusion.org_id == current_user.org_id)
    if year_group:
        q = q.where(ReportSubjectExclusion.year_group == year_group)
    rows = (await db.execute(q.order_by(ReportSubjectExclusion.year_group))).scalars().all()
    names = {s.id: s.name for s in (await db.execute(
        select(Subject).where(Subject.org_id == current_user.org_id))).scalars().all()}
    return [SubjectExclusionResponse(id=r.id, year_group=r.year_group, subject_id=r.subject_id,
                                     subject_name=names.get(r.subject_id)) for r in rows]


@router.post("/report-subject-exclusions", response_model=SubjectExclusionResponse, status_code=201, dependencies=[_write])
async def create_subject_exclusion(payload: SubjectExclusionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    subj = (await db.execute(select(Subject).where(Subject.id == payload.subject_id, Subject.org_id == current_user.org_id))).scalar_one_or_none()
    if not subj:
        raise HTTPException(status_code=422, detail="subject_id: not a subject in your organisation")
    dupe = (await db.execute(select(ReportSubjectExclusion.id).where(
        ReportSubjectExclusion.org_id == current_user.org_id, ReportSubjectExclusion.year_group == payload.year_group,
        ReportSubjectExclusion.subject_id == payload.subject_id))).scalar_one_or_none()
    if dupe:
        raise HTTPException(status_code=409, detail="That subject is already excluded for this year group.")
    r = ReportSubjectExclusion(org_id=current_user.org_id, year_group=payload.year_group, subject_id=payload.subject_id)
    db.add(r)
    await db.flush()
    return SubjectExclusionResponse(id=r.id, year_group=r.year_group, subject_id=r.subject_id, subject_name=subj.name)


@router.delete("/report-subject-exclusions/{exclusion_id}", status_code=204, dependencies=[_write])
async def delete_subject_exclusion(exclusion_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(ReportSubjectExclusion).where(
        ReportSubjectExclusion.id == exclusion_id, ReportSubjectExclusion.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Exclusion not found.")
    await db.delete(r)


# ── Secondary Report S-2: Assessment Group ───────────────────────────────────

def _agroup_response(g: AssessmentGroup) -> AssessmentGroupResponse:
    return AssessmentGroupResponse(id=g.id, name=g.name, position=g.position)


@router.get("/assessment-groups", response_model=list[AssessmentGroupResponse], dependencies=[_school_read])
async def list_assessment_groups(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(AssessmentGroup).where(AssessmentGroup.org_id == current_user.org_id)
                             .order_by(AssessmentGroup.position, AssessmentGroup.name))).scalars().all()
    return [_agroup_response(g) for g in rows]


@router.post("/assessment-groups", response_model=AssessmentGroupResponse, status_code=201, dependencies=[_write])
async def create_assessment_group(payload: AssessmentGroupCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    dupe = (await db.execute(select(AssessmentGroup.id).where(
        AssessmentGroup.org_id == current_user.org_id, func.lower(AssessmentGroup.name) == payload.name.lower()))).scalar_one_or_none()
    if dupe:
        raise HTTPException(status_code=409, detail="An assessment group with that name already exists.")
    g = AssessmentGroup(org_id=current_user.org_id, **payload.model_dump())
    db.add(g)
    await db.flush()
    return _agroup_response(g)


@router.patch("/assessment-groups/{group_id}", response_model=AssessmentGroupResponse, dependencies=[_write])
async def update_assessment_group(group_id: str, payload: AssessmentGroupUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    g = (await db.execute(select(AssessmentGroup).where(AssessmentGroup.id == group_id, AssessmentGroup.org_id == current_user.org_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Assessment group not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(g, f, v)
    await db.flush()
    return _agroup_response(g)


@router.delete("/assessment-groups/{group_id}", status_code=204, dependencies=[_write])
async def delete_assessment_group(group_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    g = (await db.execute(select(AssessmentGroup).where(AssessmentGroup.id == group_id, AssessmentGroup.org_id == current_user.org_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Assessment group not found.")
    await db.delete(g)


# ── Secondary Report S-2: Assessment (leaf components) ───────────────────────

async def _assessment_name_maps(db: AsyncSession, org_id: str):
    terms = {t.id: t.name for t in (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == org_id))).scalars().all()}
    subs = {s.id: s.name for s in (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.org_id == org_id))).scalars().all()}
    groups = {g.id: g.name for g in (await db.execute(select(AssessmentGroup).where(AssessmentGroup.org_id == org_id))).scalars().all()}
    return terms, subs, groups


def _assessment_response(a: Assessment, terms, subs, groups) -> AssessmentResponse:
    return AssessmentResponse(
        id=a.id, name=a.name, code=a.code, max_score=a.max_score,
        term_id=a.term_id, term_name=terms.get(a.term_id),
        sub_term_id=a.sub_term_id, sub_term_name=subs.get(a.sub_term_id),
        year_group=a.year_group, decimal_places=a.decimal_places,
        group_id=a.group_id, group_name=(groups.get(a.group_id) if a.group_id else None),
        position=a.position,
    )


async def _validate_assessment_fks(db, org_id, term_id, sub_term_id, group_id):
    if term_id is not None:
        ok = (await db.execute(select(AcademicTerm.id).where(AcademicTerm.id == term_id, AcademicTerm.org_id == org_id))).scalar_one_or_none()
        if not ok:
            raise HTTPException(status_code=422, detail="term_id: not a term in your organisation")
    if sub_term_id is not None:
        ok = (await db.execute(select(AcademicSubTerm.id).where(AcademicSubTerm.id == sub_term_id, AcademicSubTerm.org_id == org_id))).scalar_one_or_none()
        if not ok:
            raise HTTPException(status_code=422, detail="sub_term_id: not a sub-term in your organisation")
    if group_id:
        ok = (await db.execute(select(AssessmentGroup.id).where(AssessmentGroup.id == group_id, AssessmentGroup.org_id == org_id))).scalar_one_or_none()
        if not ok:
            raise HTTPException(status_code=422, detail="group_id: not an assessment group in your organisation")


@router.get("/assessments", response_model=list[AssessmentResponse], dependencies=[_school_read])
async def list_assessments(term_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(Assessment).where(Assessment.org_id == current_user.org_id)
    if term_id:
        q = q.where(Assessment.term_id == term_id)
    rows = (await db.execute(q.order_by(Assessment.position, Assessment.name))).scalars().all()
    terms, subs, groups = await _assessment_name_maps(db, current_user.org_id)
    return [_assessment_response(a, terms, subs, groups) for a in rows]


@router.post("/assessments", response_model=AssessmentResponse, status_code=201, dependencies=[_write])
async def create_assessment(payload: AssessmentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    await _validate_assessment_fks(db, current_user.org_id, payload.term_id, payload.sub_term_id, payload.group_id)
    a = Assessment(org_id=current_user.org_id, **payload.model_dump())
    db.add(a)
    await db.flush()
    terms, subs, groups = await _assessment_name_maps(db, current_user.org_id)
    return _assessment_response(a, terms, subs, groups)


@router.patch("/assessments/{assessment_id}", response_model=AssessmentResponse, dependencies=[_write])
async def update_assessment(assessment_id: str, payload: AssessmentUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(Assessment).where(Assessment.id == assessment_id, Assessment.org_id == current_user.org_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    data = payload.model_dump(exclude_unset=True)
    await _validate_assessment_fks(db, current_user.org_id, data.get("term_id"), data.get("sub_term_id"), data.get("group_id"))
    for f, v in data.items():
        setattr(a, f, v)
    await db.flush()
    terms, subs, groups = await _assessment_name_maps(db, current_user.org_id)
    return _assessment_response(a, terms, subs, groups)


@router.delete("/assessments/{assessment_id}", status_code=204, dependencies=[_write])
async def delete_assessment(assessment_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(Assessment).where(Assessment.id == assessment_id, Assessment.org_id == current_user.org_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    await db.delete(a)


# Fairview's curated component set per term: CBT+THEORY (20 each) at Half-Term,
# PRJ+PBT (10) + EXAM (60) at Full-Term. This is the "HALF TERM TOTAL 40" card.
_BOOTSTRAP_HALF = [("CBT", "CBT", 20), ("THEORY", "THY", 20)]
_BOOTSTRAP_FULL = [("PRJ", "PRJ", 10), ("PBT", "PBT", 10), ("EXAM", "EXM", 60)]


@router.post("/assessments/bootstrap", response_model=list[AssessmentResponse], dependencies=[_write])
async def bootstrap_assessments(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Idempotently seed the curated Fairview assessment set for every term:
    CBT+Theory at the Half-Term sub-term, PRJ+PBT+EXAM at the Full-Term. Requires
    terms + sub-terms to exist (Terms & Sub-term bootstrap first)."""
    org = current_user.org_id
    terms = (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == org))).scalars().all()
    subs = (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.org_id == org))).scalars().all()
    half = next((s for s in subs if "half" in s.name.lower() or "mid" in s.name.lower()), None)
    full = next((s for s in subs if "full" in s.name.lower()), None)
    if not terms or not half or not full:
        raise HTTPException(status_code=422, detail="Seed Terms & Sub-term (Half-Term + Full-Term) first.")

    existing = (await db.execute(select(Assessment).where(Assessment.org_id == org))).scalars().all()
    have = {(e.term_id, e.sub_term_id, (e.name or "").lower()) for e in existing}

    for t in terms:
        for pos, (name, code, mx) in enumerate(_BOOTSTRAP_HALF):
            if (t.id, half.id, name.lower()) not in have:
                db.add(Assessment(org_id=org, name=name, code=code, max_score=mx, term_id=t.id,
                                  sub_term_id=half.id, decimal_places=0, position=pos))
        for pos, (name, code, mx) in enumerate(_BOOTSTRAP_FULL):
            if (t.id, full.id, name.lower()) not in have:
                db.add(Assessment(org_id=org, name=name, code=code, max_score=mx, term_id=t.id,
                                  sub_term_id=full.id, decimal_places=0, position=pos))
    await db.flush()
    rows = (await db.execute(select(Assessment).where(Assessment.org_id == org).order_by(Assessment.position, Assessment.name))).scalars().all()
    tmap, smap, gmap = await _assessment_name_maps(db, org)
    return [_assessment_response(a, tmap, smap, gmap) for a in rows]


# ── Secondary Report S-3: Cumulative curated engine ──────────────────────────

async def _cumul_label_maps(db: AsyncSession, org_id: str):
    terms = {t.id: t.name for t in (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == org_id))).scalars().all()}
    subs = {s.id: s.name for s in (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.org_id == org_id))).scalars().all()}
    a_names = {a.id: a.name for a in (await db.execute(select(Assessment).where(Assessment.org_id == org_id))).scalars().all()}
    c_names = {c.id: c.name for c in (await db.execute(select(Cumulative).where(Cumulative.org_id == org_id))).scalars().all()}
    return terms, subs, a_names, c_names


def _component_label(comp: CumulativeComponent, a_names, c_names) -> str | None:
    return (a_names if comp.ref_type == "assessment" else c_names).get(comp.ref_id)


async def _cumulative_response(db, org_id, c: Cumulative, terms, subs, a_names, c_names) -> CumulativeResponse:
    comps = (await db.execute(select(CumulativeComponent).where(
        CumulativeComponent.cumulative_id == c.id, CumulativeComponent.org_id == org_id)
        .order_by(CumulativeComponent.position))).scalars().all()
    return CumulativeResponse(
        id=c.id, name=c.name, code=c.code, term_id=c.term_id, term_name=terms.get(c.term_id),
        sub_term_id=c.sub_term_id, sub_term_name=subs.get(c.sub_term_id), year_group=c.year_group,
        cumul_type=c.cumul_type, max_percent=c.max_percent, decimal_places=c.decimal_places, position=c.position,
        components=[CumulComponentOut(ref_type=cm.ref_type, ref_id=cm.ref_id, label=_component_label(cm, a_names, c_names)) for cm in comps],
    )


async def _validate_component(db, org_id, comp: CumulComponentIn):
    if comp.ref_type not in REF_TYPES:
        raise HTTPException(status_code=422, detail=f"ref_type must be one of {sorted(REF_TYPES)}")
    model = Assessment if comp.ref_type == "assessment" else Cumulative
    ok = (await db.execute(select(model.id).where(model.id == comp.ref_id, model.org_id == org_id))).scalar_one_or_none()
    if not ok:
        raise HTTPException(status_code=422, detail=f"{comp.ref_type} component not found in your organisation")


@router.get("/cumulatives", response_model=list[CumulativeResponse], dependencies=[_school_read])
async def list_cumulatives(term_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(Cumulative).where(Cumulative.org_id == current_user.org_id)
    if term_id:
        q = q.where(Cumulative.term_id == term_id)
    rows = (await db.execute(q.order_by(Cumulative.position, Cumulative.name))).scalars().all()
    terms, subs, a_names, c_names = await _cumul_label_maps(db, current_user.org_id)
    return [await _cumulative_response(db, current_user.org_id, c, terms, subs, a_names, c_names) for c in rows]


@router.post("/cumulatives", response_model=CumulativeResponse, status_code=201, dependencies=[_write])
async def create_cumulative(payload: CumulativeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    if payload.cumul_type not in CUMUL_TYPES:
        raise HTTPException(status_code=422, detail=f"cumul_type must be one of {sorted(CUMUL_TYPES)}")
    await _validate_assessment_fks(db, org, payload.term_id, payload.sub_term_id, None)
    for comp in payload.components:
        await _validate_component(db, org, comp)
    data = payload.model_dump(exclude={"components"})
    c = Cumulative(org_id=org, **data)
    db.add(c)
    await db.flush()
    for i, comp in enumerate(payload.components):
        db.add(CumulativeComponent(org_id=org, cumulative_id=c.id, ref_type=comp.ref_type, ref_id=comp.ref_id, position=i))
    await db.flush()
    terms, subs, a_names, c_names = await _cumul_label_maps(db, org)
    return await _cumulative_response(db, org, c, terms, subs, a_names, c_names)


@router.patch("/cumulatives/{cumulative_id}", response_model=CumulativeResponse, dependencies=[_write])
async def update_cumulative(cumulative_id: str, payload: CumulativeUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(Cumulative).where(Cumulative.id == cumulative_id, Cumulative.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Cumulative not found.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("cumul_type") and data["cumul_type"] not in CUMUL_TYPES:
        raise HTTPException(status_code=422, detail=f"cumul_type must be one of {sorted(CUMUL_TYPES)}")
    for f, v in data.items():
        setattr(c, f, v)
    await db.flush()
    terms, subs, a_names, c_names = await _cumul_label_maps(db, current_user.org_id)
    return await _cumulative_response(db, current_user.org_id, c, terms, subs, a_names, c_names)


@router.put("/cumulatives/{cumulative_id}/components", response_model=CumulativeResponse, dependencies=[_write])
async def replace_cumulative_components(cumulative_id: str, components: list[CumulComponentIn], db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    c = (await db.execute(select(Cumulative).where(Cumulative.id == cumulative_id, Cumulative.org_id == org))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Cumulative not found.")
    for comp in components:
        await _validate_component(db, org, comp)
    existing = (await db.execute(select(CumulativeComponent).where(CumulativeComponent.cumulative_id == cumulative_id, CumulativeComponent.org_id == org))).scalars().all()
    for e in existing:
        await db.delete(e)
    await db.flush()
    for i, comp in enumerate(components):
        db.add(CumulativeComponent(org_id=org, cumulative_id=cumulative_id, ref_type=comp.ref_type, ref_id=comp.ref_id, position=i))
    await db.flush()
    terms, subs, a_names, c_names = await _cumul_label_maps(db, org)
    return await _cumulative_response(db, org, c, terms, subs, a_names, c_names)


@router.delete("/cumulatives/{cumulative_id}", status_code=204, dependencies=[_write])
async def delete_cumulative(cumulative_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(Cumulative).where(Cumulative.id == cumulative_id, Cumulative.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Cumulative not found.")
    await db.delete(c)


@router.post("/cumulatives/bootstrap", response_model=list[CumulativeResponse], dependencies=[_write])
async def bootstrap_cumulatives(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Seed Fairview's curated cumulative columns per term over the S-2 assessments:
    HALF TERM TOTAL(CBT+Theory), %(CBT+Theory), CA 1 = custom% max 20 of HALF TERM
    TOTAL, and TOTAL(CA 1 + PRJ + PBT + EXAM). Needs the assessment set seeded first."""
    org = current_user.org_id
    terms = (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == org))).scalars().all()
    assessments = (await db.execute(select(Assessment).where(Assessment.org_id == org))).scalars().all()
    if not terms or not assessments:
        raise HTTPException(status_code=422, detail="Seed Terms and the Assessment set first.")

    existing = (await db.execute(select(Cumulative).where(Cumulative.org_id == org))).scalars().all()
    have = {(e.term_id, (e.name or "").lower()) for e in existing}

    def asmt(term_id, name):
        return next((a for a in assessments if a.term_id == term_id and (a.name or "").lower() == name.lower()), None)

    async def make(term_id, sub_term_id, name, cumul_type, comps, max_percent=None):
        if (term_id, name.lower()) in have:
            return next(c for c in (await db.execute(select(Cumulative).where(
                Cumulative.org_id == org, Cumulative.term_id == term_id, func.lower(Cumulative.name) == name.lower()))).scalars().all())
        c = Cumulative(org_id=org, name=name, term_id=term_id, sub_term_id=sub_term_id,
                       cumul_type=cumul_type, max_percent=max_percent, decimal_places=0)
        db.add(c)
        await db.flush()
        for i, (rt, rid) in enumerate(comps):
            db.add(CumulativeComponent(org_id=org, cumulative_id=c.id, ref_type=rt, ref_id=rid, position=i))
        await db.flush()
        have.add((term_id, name.lower()))
        return c

    for t in terms:
        cbt, thy = asmt(t.id, "CBT"), asmt(t.id, "THEORY")
        prj, pbt, exam = asmt(t.id, "PRJ"), asmt(t.id, "PBT"), asmt(t.id, "EXAM")
        if not all([cbt, thy, prj, pbt, exam]):
            continue
        half_sub, full_sub = cbt.sub_term_id, exam.sub_term_id
        htt = await make(t.id, half_sub, "HALF TERM TOTAL", "score", [("assessment", cbt.id), ("assessment", thy.id)])
        await make(t.id, half_sub, "%", "percentage", [("assessment", cbt.id), ("assessment", thy.id)])
        # CA 1 (the continuous-assessment carried into the full-term result) is a
        # FULL-TERM column even though it rescales the half-term total.
        ca1 = await make(t.id, full_sub, "CA 1", "custom_percentage", [("cumulative", htt.id)], max_percent=20)
        await make(t.id, full_sub, "TOTAL", "score",
                   [("cumulative", ca1.id), ("assessment", prj.id), ("assessment", pbt.id), ("assessment", exam.id)])

    rows = (await db.execute(select(Cumulative).where(Cumulative.org_id == org).order_by(Cumulative.position, Cumulative.name))).scalars().all()
    tmap, smap, amap, cmap = await _cumul_label_maps(db, org)
    return [await _cumulative_response(db, org, c, tmap, smap, amap, cmap) for c in rows]


# ── Secondary Report S-4a: Report Entry (assessment scores) ──────────────────

async def _entry_assessments(db, org_id, term_id, level):
    """Assessments for a term that apply to a class level (year_group NULL = all)."""
    q = select(Assessment).where(Assessment.org_id == org_id, Assessment.term_id == term_id)
    rows = (await db.execute(q.order_by(Assessment.position, Assessment.name))).scalars().all()
    return [a for a in rows if not a.year_group or a.year_group == level]


@router.get("/my-teaching-assignments", response_model=list[TeachingAssignment], dependencies=[_school_read])
async def my_teaching_assignments(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """The (class, subject) pairs the signed-in teacher teaches (from the Timetable)
    — the source for the teacher-facing Make Report page."""
    org = current_user.org_id
    pairs = await _teacher_assignments(db, org, current_user.id)
    if not pairs:
        return []
    cls_names = {c.id: c.name for c in (await db.execute(select(SchoolClass).where(SchoolClass.org_id == org))).scalars().all()}
    subj_names = {s.id: s.name for s in (await db.execute(select(Subject).where(Subject.org_id == org))).scalars().all()}
    out = [TeachingAssignment(class_id=cid, class_name=cls_names.get(cid), subject_id=sid, subject_name=subj_names.get(sid))
           for (cid, sid) in pairs]
    out.sort(key=lambda a: (a.class_name or "", a.subject_name or ""))
    return out


@router.get("/report-entry", response_model=ReportEntryGrid, dependencies=[_school_read])
async def report_entry_grid(class_id: str, subject_id: str, term_id: str,
                            db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.org_id == org))).scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found.")
    # Section-scoping: a teacher may only access classes in their assigned section(s).
    if not _report_admin(current_user) and cls.section_id:
        teacher_sections = (await db.execute(
            select(TeacherSection.section_id).where(
                TeacherSection.teacher_id == current_user.id,
                TeacherSection.org_id == org,
            )
        )).scalars().all()
        if cls.section_id not in teacher_sections:
            raise HTTPException(status_code=403, detail="You do not teach in this academic section.")
    # Teacher scoping: a non-admin may only touch subjects they teach in this class.
    if not _report_admin(current_user) and (class_id, subject_id) not in await _teacher_assignments(db, org, current_user.id):
        raise HTTPException(status_code=403, detail="You do not teach this subject in this class.")
    subs = {s.id: s.name for s in (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.org_id == org))).scalars().all()}
    assessments = await _entry_assessments(db, org, term_id, getattr(cls, "level", None))
    students = (await db.execute(
        select(Student).where(
            Student.org_id == org, Student.class_id == class_id, Student.is_deleted == False)  # noqa: E712
        .order_by(Student.first_name, Student.last_name)
    )).scalars().all()
    a_ids = [a.id for a in assessments]
    s_ids = [s.id for s in students]
    scores: dict[str, dict[str, object]] = {sid: {} for sid in s_ids}
    if a_ids and s_ids:
        rows = (await db.execute(select(StudentAssessmentScore).where(
            StudentAssessmentScore.org_id == org, StudentAssessmentScore.subject_id == subject_id,
            StudentAssessmentScore.assessment_id.in_(a_ids), StudentAssessmentScore.student_id.in_(s_ids)))).scalars().all()
        for r in rows:
            scores.setdefault(r.student_id, {})[r.assessment_id] = r.score
    return ReportEntryGrid(
        class_id=class_id, subject_id=subject_id, term_id=term_id,
        assessments=[ReportEntryAssessment(id=a.id, name=a.name, max_score=a.max_score, sub_term_name=subs.get(a.sub_term_id)) for a in assessments],
        students=[ReportEntryStudent(id=s.id, name=f"{s.first_name} {s.last_name}".strip()) for s in students],
        scores=scores,
    )


@router.post("/report-entry", dependencies=[_reports_write])
async def save_report_entry(payload: ReportEntrySave, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    subj = (await db.execute(select(Subject.id).where(Subject.id == payload.subject_id, Subject.org_id == org))).scalar_one_or_none()
    if not subj:
        raise HTTPException(status_code=422, detail="subject_id: not a subject in your organisation")
    # Teacher scoping: a non-admin may only save scores for a (class, subject) they
    # actually teach. class_id is required for a non-admin so the scope is checkable.
    if not _report_admin(current_user):
        if not payload.class_id:
            raise HTTPException(status_code=422, detail="class_id is required.")
        # Section-scoping: teacher may only save scores for classes in their assigned section(s).
        cls = (await db.execute(select(SchoolClass).where(SchoolClass.id == payload.class_id, SchoolClass.org_id == org))).scalar_one_or_none()
        if cls and cls.section_id:
            teacher_sections = (await db.execute(
                select(TeacherSection.section_id).where(
                    TeacherSection.teacher_id == current_user.id,
                    TeacherSection.org_id == org,
                )
            )).scalars().all()
            if cls.section_id not in teacher_sections:
                raise HTTPException(status_code=403, detail="You do not teach in this academic section.")
        if (payload.class_id, payload.subject_id) not in await _teacher_assignments(db, org, current_user.id):
            raise HTTPException(status_code=403, detail="You do not teach this subject in this class.")
    valid_assessments = set((await db.execute(select(Assessment.id).where(Assessment.org_id == org))).scalars().all())
    keys = {(i.student_id, i.assessment_id) for i in payload.items}
    existing = {(r.student_id, r.assessment_id): r for r in (await db.execute(select(StudentAssessmentScore).where(
        StudentAssessmentScore.org_id == org, StudentAssessmentScore.subject_id == payload.subject_id))).scalars().all()
        if (r.student_id, r.assessment_id) in keys}
    saved = 0
    for it in payload.items:
        if it.assessment_id not in valid_assessments:
            continue
        row = existing.get((it.student_id, it.assessment_id))
        if row:
            row.score = it.score
            row.recorded_by = current_user.id
        else:
            db.add(StudentAssessmentScore(org_id=org, student_id=it.student_id, subject_id=payload.subject_id,
                                          assessment_id=it.assessment_id, score=it.score, recorded_by=current_user.id))
        saved += 1
    await db.flush()
    return {"saved": saved}


# ── Secondary Report S-4b: Broadsheet (class results grid) ───────────────────

def _grade_for(pct, bands):
    """First numeric band whose [min,max] contains pct (max None = open top)."""
    from decimal import Decimal as _Dec
    p = _Dec(str(pct))
    for b in bands:
        lo = b.min_score if b.min_score is not None else _Dec("-999999")
        hi = b.max_score if b.max_score is not None else _Dec("999999")
        if lo <= p <= hi:
            return b.grade
    return None


def _pick_display_cumulative(cumulatives, sub_term_id):
    for_sub = [c for c in cumulatives if c.sub_term_id == sub_term_id]
    for c in for_sub:
        if (c.name or "").strip().upper() == "TOTAL":
            return c
    if for_sub:
        return max(for_sub, key=lambda c: (c.position or 0))
    if cumulatives:
        return max(cumulatives, key=lambda c: (c.position or 0))
    return None


@router.get("/report-broadsheet", response_model=BroadsheetResponse, dependencies=[Depends(PermissionChecker("school:reports:read"))])
async def report_broadsheet(class_id: str, term_id: str, sub_term_id: str,
                            db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.org_id == org))).scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found.")
    # Class-teacher gate: a non-admin sees a class's results only if they are its
    # class/form teacher (Educare: "You are not a class teacher").
    if not _report_admin(current_user) and cls.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the class teacher for this class.")
    # Section-scoping: a teacher may only view reports for their assigned section(s).
    if not _report_admin(current_user) and cls.section_id:
        teacher_sections = (await db.execute(
            select(TeacherSection.section_id).where(
                TeacherSection.teacher_id == current_user.id,
                TeacherSection.org_id == org,
            )
        )).scalars().all()
        if cls.section_id not in teacher_sections:
            raise HTTPException(status_code=403, detail="You do not teach in this academic section.")
    level = getattr(cls, "level", None)
    term_name = (await db.execute(select(AcademicTerm.name).where(AcademicTerm.id == term_id, AcademicTerm.org_id == org))).scalar_one_or_none()
    sub_name = (await db.execute(select(AcademicSubTerm.name).where(AcademicSubTerm.id == sub_term_id, AcademicSubTerm.org_id == org))).scalar_one_or_none()

    students = (await db.execute(
        select(Student).where(Student.org_id == org, Student.class_id == class_id, Student.is_deleted == False)  # noqa: E712
        .order_by(Student.first_name, Student.last_name)
    )).scalars().all()
    s_ids = [s.id for s in students]

    # Config for the term: assessments, cumulatives (+ components), grade scale.
    assessments = {a.id: a for a in (await db.execute(select(Assessment).where(
        Assessment.org_id == org, Assessment.term_id == term_id))).scalars().all()}
    cumulatives = (await db.execute(select(Cumulative).where(Cumulative.org_id == org, Cumulative.term_id == term_id))).scalars().all()
    cumul_by_id = {c.id: c for c in cumulatives}
    comp_rows = (await db.execute(select(CumulativeComponent).where(CumulativeComponent.org_id == org)
                                  .order_by(CumulativeComponent.position))).scalars().all()
    components: dict[str, list] = {}
    for cr in comp_rows:
        components.setdefault(cr.cumulative_id, []).append((cr.ref_type, cr.ref_id))

    scale = (await db.execute(select(GradingScale).where(
        GradingScale.org_id == org, GradingScale.scale_type == "numeric", GradingScale.purpose == "grade")
        .order_by(GradingScale.show_in_table.desc()))).scalars().first()
    bands = []
    if scale:
        bands = sorted((await db.execute(select(GradingBand).where(GradingBand.scale_id == scale.id, GradingBand.org_id == org))).scalars().all(),
                       key=lambda b: -(b.max_score or 0))

    display = _pick_display_cumulative(cumulatives, sub_term_id)

    # All scores for this class's pupils, indexed by (student, subject, assessment).
    score_map: dict[tuple, object] = {}
    subj_ids: set[str] = set()
    if s_ids and assessments:
        rows = (await db.execute(select(StudentAssessmentScore).where(
            StudentAssessmentScore.org_id == org, StudentAssessmentScore.student_id.in_(s_ids),
            StudentAssessmentScore.assessment_id.in_(list(assessments.keys()))))).scalars().all()
        for r in rows:
            score_map[(r.student_id, r.subject_id, r.assessment_id)] = r.score
            subj_ids.add(r.subject_id)

    subj_names = {s.id: s.name for s in (await db.execute(select(Subject).where(Subject.org_id == org, Subject.id.in_(subj_ids or ["_none_"])))).scalars().all()}
    subjects = sorted(({"id": sid, "name": subj_names.get(sid, sid)} for sid in subj_ids), key=lambda x: x["name"])

    band_out = [BroadsheetBand(grade=b.grade, min_score=b.min_score, max_score=b.max_score, remark=b.remark) for b in bands]
    rows_out: list[BroadsheetRow] = []
    for s in students:
        cells: dict[str, BroadsheetCell] = {}
        total = money(0)
        pct_sum = money(0)
        n = 0
        for sub in subjects:
            sid = sub["id"]
            if not display:
                continue
            scores = {aid: score_map.get((s.id, sid, aid)) for aid in assessments}
            val, mx = evaluate_cumulative(display.id, cumul_by_id, components, assessments, scores)
            has_any = any(score_map.get((s.id, sid, aid)) is not None for aid in assessments)
            if not has_any:
                cells[sid] = BroadsheetCell(value=None, grade=None)
                continue
            pct = (val / mx * 100) if mx else money(0)
            g = _grade_for(pct, bands)
            cells[sid] = BroadsheetCell(value=round_dp(val, display.decimal_places or 0), grade=g)
            total += val
            pct_sum += pct
            n += 1
        average = (pct_sum / n) if n else money(0)
        rows_out.append(BroadsheetRow(
            student_id=s.id, student_name=f"{s.first_name} {s.last_name}".strip(), subjects=cells,
            total=round_dp(total, 2), average=round_dp(average, 2), grade=_grade_for(average, bands) if n else None,
        ))

    rows_out.sort(key=lambda r: r.total, reverse=True)
    for i, r in enumerate(rows_out, start=1):
        r.position = i

    return BroadsheetResponse(
        class_id=class_id, class_name=cls.name, term_name=term_name, sub_term_name=sub_name,
        display_cumulative=(display.name if display else None),
        subjects=[BroadsheetSubject(**s) for s in subjects], bands=band_out, rows=rows_out,
    )


# ── Secondary Report S-4c: printable report card (one pupil) ─────────────────

@router.get("/report-card", response_model=ReportCardResponse, dependencies=[Depends(PermissionChecker("school:reports:read"))])
async def report_card(student_id: str, term_id: str, sub_term_id: str,
                      db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    student = (await db.execute(select(Student).where(Student.id == student_id, Student.org_id == org))).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.id == student.class_id, SchoolClass.org_id == org))).scalar_one_or_none()
    # Class-teacher gate: a non-admin may only open a card for a pupil in the class
    # they are the class/form teacher of.
    if not _report_admin(current_user) and (not cls or cls.teacher_id != current_user.id):
        raise HTTPException(status_code=403, detail="You are not the class teacher for this pupil's class.")
    # Section-scoping: a teacher may only view reports for their assigned section(s).
    # For example, a Secondary teacher should not access Primary/Nursery report data.
    if not _report_admin(current_user) and cls and cls.section_id:
        teacher_sections = (await db.execute(
            select(TeacherSection.section_id).where(
                TeacherSection.teacher_id == current_user.id,
                TeacherSection.org_id == org,
            )
        )).scalars().all()
        if cls.section_id not in teacher_sections:
            raise HTTPException(status_code=403, detail="You do not teach in this academic section.")
    term_name = (await db.execute(select(AcademicTerm.name).where(AcademicTerm.id == term_id, AcademicTerm.org_id == org))).scalar_one_or_none()
    sub_name = (await db.execute(select(AcademicSubTerm.name).where(AcademicSubTerm.id == sub_term_id, AcademicSubTerm.org_id == org))).scalar_one_or_none()
    branding = _branding_response((await db.execute(select(ReportBranding).where(ReportBranding.org_id == org))).scalar_one_or_none())

    # Config: assessments + cumulatives for the term; the columns for this sub-term.
    assessments = {a.id: a for a in (await db.execute(select(Assessment).where(Assessment.org_id == org, Assessment.term_id == term_id))).scalars().all()}
    cumulatives = (await db.execute(select(Cumulative).where(Cumulative.org_id == org, Cumulative.term_id == term_id))).scalars().all()
    cumul_by_id = {c.id: c for c in cumulatives}
    comp_rows = (await db.execute(select(CumulativeComponent).where(CumulativeComponent.org_id == org).order_by(CumulativeComponent.position))).scalars().all()
    components: dict[str, list] = {}
    for cr in comp_rows:
        components.setdefault(cr.cumulative_id, []).append((cr.ref_type, cr.ref_id))

    scale = (await db.execute(select(GradingScale).where(
        GradingScale.org_id == org, GradingScale.scale_type == "numeric", GradingScale.purpose == "grade")
        .order_by(GradingScale.show_in_table.desc()))).scalars().first()
    bands = sorted((await db.execute(select(GradingBand).where(GradingBand.scale_id == scale.id, GradingBand.org_id == org))).scalars().all(),
                   key=lambda b: -(b.max_score or 0)) if scale else []

    asmt_cols = sorted([a for a in assessments.values() if a.sub_term_id == sub_term_id], key=lambda a: (a.position or 0, a.name))
    cumul_cols = sorted([c for c in cumulatives if c.sub_term_id == sub_term_id], key=lambda c: (c.position or 0, c.name))
    display = _pick_display_cumulative(cumulatives, sub_term_id)
    columns = ([CardColumn(key=a.id, name=a.name, kind="assessment", max_score=a.max_score) for a in asmt_cols]
               + [CardColumn(key=c.id, name=c.name, kind="cumulative") for c in cumul_cols])

    # All classmates' scores (for arm average + position).
    classmates = (await db.execute(select(Student).where(
        Student.org_id == org, Student.class_id == student.class_id, Student.is_deleted == False))).scalars().all()  # noqa: E712
    cm_ids = [s.id for s in classmates]
    score_map: dict[tuple, object] = {}
    subj_ids: set[str] = set()
    if cm_ids and assessments:
        rows = (await db.execute(select(StudentAssessmentScore).where(
            StudentAssessmentScore.org_id == org, StudentAssessmentScore.student_id.in_(cm_ids),
            StudentAssessmentScore.assessment_id.in_(list(assessments.keys()))))).scalars().all()
        for r in rows:
            score_map[(r.student_id, r.subject_id, r.assessment_id)] = r.score
            subj_ids.add(r.subject_id)

    subj_names = {s.id: s.name for s in (await db.execute(select(Subject).where(Subject.org_id == org, Subject.id.in_(subj_ids or ["_none_"])))).scalars().all()}
    subjects = sorted(subj_ids, key=lambda sid: subj_names.get(sid, sid))

    def display_val(sid_student, sid_subject):
        if not display:
            return None, None
        if not any(score_map.get((sid_student, sid_subject, aid)) is not None for aid in assessments):
            return None, None
        scores = {aid: score_map.get((sid_student, sid_subject, aid)) for aid in assessments}
        return evaluate_cumulative(display.id, cumul_by_id, components, assessments, scores)

    # Per-classmate totals (for position) + per-subject class values (arm average).
    totals: dict[str, object] = {}
    arm: dict[str, list] = {}
    for st in classmates:
        tot = money(0)
        for sid in subjects:
            v, _mx = display_val(st.id, sid)
            if v is not None:
                tot += v
                arm.setdefault(sid, []).append(v)
        totals[st.id] = tot
    ranking = sorted(classmates, key=lambda s: totals.get(s.id, money(0)), reverse=True)
    position = next((i for i, s in enumerate(ranking, start=1) if s.id == student_id), 0)

    # This pupil's detailed rows.
    subj_rows: list[CardSubjectRow] = []
    pct_sum = money(0)
    n = 0
    my_total = money(0)
    for sid in subjects:
        if not any(score_map.get((student_id, sid, aid)) is not None for aid in assessments):
            continue
        scores = {aid: score_map.get((student_id, sid, aid)) for aid in assessments}
        values: dict[str, object] = {}
        for a in asmt_cols:
            values[a.id] = scores.get(a.id)
        for c in cumul_cols:
            v, _m = evaluate_cumulative(c.id, cumul_by_id, components, assessments, scores)
            values[c.id] = round_dp(v, c.decimal_places or 0)
        dval, dmax = evaluate_cumulative(display.id, cumul_by_id, components, assessments, scores) if display else (money(0), money(0))
        pct = (dval / dmax * 100) if dmax else money(0)
        g = _grade_for(pct, bands)
        remark = next((b.remark for b in bands if b.grade == g), None)
        vals_list = arm.get(sid, [])
        arm_avg = round_dp(sum(vals_list) / len(vals_list), 2) if vals_list else None
        subj_rows.append(CardSubjectRow(subject_id=sid, subject_name=subj_names.get(sid, sid), values=values,
                                        grade=g, remark=remark, subject_arm_average=arm_avg))
        my_total += dval
        pct_sum += pct
        n += 1
    average = (pct_sum / n) if n else money(0)

    sr = (await db.execute(select(StudentReport).where(
        StudentReport.org_id == org, StudentReport.student_id == student_id))).scalars().first()

    comment_rows = (await db.execute(select(StudentReportComment).where(
        StudentReportComment.org_id == org, StudentReportComment.student_id == student_id,
        StudentReportComment.term_id == term_id, StudentReportComment.sub_term_id == sub_term_id))).scalars().all()
    comments = {c.kind: c.text for c in comment_rows}

    title = " ".join(x for x in [(term_name or "").upper(), (sub_name or "").upper(), "REPORT"] if x).strip()
    return ReportCardResponse(
        student_id=student_id, student_name=f"{student.first_name} {student.last_name}".strip(),
        admission_no=student.student_id, photo_url=getattr(student, "photo_url", None),
        class_name=(cls.name if cls else None), term_name=term_name, sub_term_name=sub_name, report_title=title,
        branding=branding, columns=columns,
        subjects=subj_rows, bands=[BroadsheetBand(grade=b.grade, min_score=b.min_score, max_score=b.max_score, remark=b.remark) for b in bands],
        total=round_dp(my_total, 2), average=round_dp(average, 2), grade=_grade_for(average, bands) if n else None,
        position=position, class_size=len(classmates),
        attendance_present=(sr.attendance_present if sr else None), attendance_total=(sr.attendance_total if sr else None),
        head_comment=comments.get("head"), pc_comment=comments.get("pc"),
    )


# ── Secondary Report S-4d: report-card comment grids (Head / PC Teacher) ─────

@router.get("/report-comments", response_model=CommentGridResponse, dependencies=[_reports_write])
async def report_comment_grid(class_id: str, term_id: str, sub_term_id: str, kind: str,
                              db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    if kind not in REPORT_COMMENT_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(REPORT_COMMENT_KINDS)}")
    await _gate_comment_access(db, org, current_user, class_id, kind)
    students = (await db.execute(
        select(Student).where(Student.org_id == org, Student.class_id == class_id, Student.is_deleted == False)  # noqa: E712
        .order_by(Student.first_name, Student.last_name)
    )).scalars().all()
    existing = {c.student_id: c.text for c in (await db.execute(select(StudentReportComment).where(
        StudentReportComment.org_id == org, StudentReportComment.term_id == term_id,
        StudentReportComment.sub_term_id == sub_term_id, StudentReportComment.kind == kind))).scalars().all()}
    return CommentGridResponse(
        class_id=class_id, term_id=term_id, sub_term_id=sub_term_id, kind=kind,
        rows=[CommentGridRow(student_id=s.id, student_name=f"{s.first_name} {s.last_name}".strip(),
                             text=existing.get(s.id)) for s in students],
    )


@router.post("/report-comments", dependencies=[_reports_write])
async def save_report_comments(payload: CommentGridSave, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    if payload.kind not in REPORT_COMMENT_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(REPORT_COMMENT_KINDS)}")
    if not _report_admin(current_user) and not payload.class_id:
        raise HTTPException(status_code=422, detail="class_id is required.")
    await _gate_comment_access(db, org, current_user, payload.class_id, payload.kind)
    ids = [i.student_id for i in payload.items]
    existing = {c.student_id: c for c in (await db.execute(select(StudentReportComment).where(
        StudentReportComment.org_id == org, StudentReportComment.term_id == payload.term_id,
        StudentReportComment.sub_term_id == payload.sub_term_id, StudentReportComment.kind == payload.kind,
        StudentReportComment.student_id.in_(ids or ["_none_"])))).scalars().all()}
    saved = 0
    for it in payload.items:
        row = existing.get(it.student_id)
        if row:
            row.text = it.text
            row.recorded_by = current_user.id
        else:
            db.add(StudentReportComment(org_id=org, student_id=it.student_id, term_id=payload.term_id,
                                        sub_term_id=payload.sub_term_id, kind=payload.kind, text=it.text,
                                        recorded_by=current_user.id))
        saved += 1
    await db.flush()
    return {"saved": saved}


# ── Secondary Report S-5: Result Insight (performance charts) ────────────────

def _mean(vals):
    return round_dp(sum(vals) / len(vals), 1) if vals else None


@router.get("/report-insight", response_model=InsightResponse, dependencies=[Depends(PermissionChecker("school_admin:read"))])
async def report_insight(term_id: str, sub_term_id: str,
                         db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """School-wide performance for a (term, sub-term): per-subject average, the same
    split by gender, and per-class average — computed through the cumulative
    evaluator over every entered score."""
    org = current_user.org_id
    term_name = (await db.execute(select(AcademicTerm.name).where(AcademicTerm.id == term_id, AcademicTerm.org_id == org))).scalar_one_or_none()
    sub_name = (await db.execute(select(AcademicSubTerm.name).where(AcademicSubTerm.id == sub_term_id, AcademicSubTerm.org_id == org))).scalar_one_or_none()

    assessments = {a.id: a for a in (await db.execute(select(Assessment).where(Assessment.org_id == org, Assessment.term_id == term_id))).scalars().all()}
    cumulatives = (await db.execute(select(Cumulative).where(Cumulative.org_id == org, Cumulative.term_id == term_id))).scalars().all()
    cumul_by_id = {c.id: c for c in cumulatives}
    comp_rows = (await db.execute(select(CumulativeComponent).where(CumulativeComponent.org_id == org).order_by(CumulativeComponent.position))).scalars().all()
    components: dict[str, list] = {}
    for cr in comp_rows:
        components.setdefault(cr.cumulative_id, []).append((cr.ref_type, cr.ref_id))
    display = _pick_display_cumulative(cumulatives, sub_term_id)

    empty = InsightResponse(term_name=term_name, sub_term_name=sub_name)
    if not display or not assessments:
        return empty

    rows = (await db.execute(select(StudentAssessmentScore).where(
        StudentAssessmentScore.org_id == org,
        StudentAssessmentScore.assessment_id.in_(list(assessments.keys()))))).scalars().all()
    if not rows:
        return empty

    # scores[(student, subject)][assessment] = score
    by_pair: dict[tuple, dict] = {}
    for r in rows:
        by_pair.setdefault((r.student_id, r.subject_id), {})[r.assessment_id] = r.score

    student_ids = {sid for sid, _ in by_pair}
    subj_ids = {sub for _, sub in by_pair}
    students = {s.id: s for s in (await db.execute(select(Student).where(Student.org_id == org, Student.id.in_(student_ids or ["_none_"])))).scalars().all()}
    subj_names = {s.id: s.name for s in (await db.execute(select(Subject).where(Subject.org_id == org, Subject.id.in_(subj_ids or ["_none_"])))).scalars().all()}
    cls_ids = {s.class_id for s in students.values() if s.class_id}
    cls_names = {c.id: c.name for c in (await db.execute(select(SchoolClass).where(SchoolClass.org_id == org, SchoolClass.id.in_(cls_ids or ["_none_"])))).scalars().all()}

    def norm_gender(g):
        g = (g or "").strip().lower()
        return "male" if g.startswith("m") else "female" if g.startswith("f") else None

    subj_pcts: dict[str, list] = {}
    gender_pcts: dict[str, dict] = {}
    student_pcts: dict[str, list] = {}     # student -> their subject pcts (for class average)
    for (sid, sub), scores in by_pair.items():
        full = {aid: scores.get(aid) for aid in assessments}
        val, mx = evaluate_cumulative(display.id, cumul_by_id, components, assessments, full)
        pct = (val / mx * 100) if mx else money(0)
        subj_pcts.setdefault(sub, []).append(pct)
        student_pcts.setdefault(sid, []).append(pct)
        g = norm_gender(getattr(students.get(sid), "gender", None))
        if g:
            gender_pcts.setdefault(sub, {"male": [], "female": []})[g].append(pct)

    subjects = sorted(subj_ids, key=lambda s: subj_names.get(s, s))
    subj_out = [InsightSubject(subject_id=s, subject_name=subj_names.get(s, s), average=_mean(subj_pcts.get(s, [])) or money(0)) for s in subjects]
    gender_out = [InsightGender(subject_id=s, subject_name=subj_names.get(s, s),
                                male=_mean(gender_pcts.get(s, {}).get("male", [])),
                                female=_mean(gender_pcts.get(s, {}).get("female", []))) for s in subjects]

    class_pcts: dict[str, list] = {}
    for sid, pcts in student_pcts.items():
        st = students.get(sid)
        if st and st.class_id and pcts:
            class_pcts.setdefault(st.class_id, []).append(sum(pcts) / len(pcts))
    classes = sorted(class_pcts.keys(), key=lambda c: cls_names.get(c, c))
    class_out = [InsightClass(class_id=c, class_name=cls_names.get(c, c), average=_mean(class_pcts.get(c, [])) or money(0)) for c in classes]

    return InsightResponse(term_name=term_name, sub_term_name=sub_name,
                           subjects=subj_out, gender=gender_out, classes=class_out)


# ── Secondary Report S-6: Reports Upload (bulk score import) ─────────────────

_UPLOAD_SKIP_COLS = {"student", "name", "student name", "admission_no", "admission", "admission no", "subject"}


@router.post("/report-upload", response_model=ScoreUploadResult, dependencies=[_report_admin_write])
async def report_upload(term_id: str, file: UploadFile = File(...),
                        db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Bulk-import scores from a CSV / Excel / Word / PDF grid. Columns
    (case-insensitive): student (name) or admission_no, subject, then one column per
    assessment (CBT, THEORY, PRJ, PBT, EXAM). Rows are matched to the term's
    assessments by name; unknown students/subjects/assessments are reported, not fatal."""
    from decimal import Decimal, InvalidOperation
    org = current_user.org_id
    content = await file.read()
    try:
        parsed = rows_from_upload(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    students = (await db.execute(select(Student).where(Student.org_id == org, Student.is_deleted == False))).scalars().all()  # noqa: E712
    by_adm = {(s.student_id or "").strip().lower(): s for s in students if s.student_id}
    by_name = {f"{s.first_name} {s.last_name}".strip().lower(): s for s in students}
    subjects_by_name = {s.name.strip().lower(): s for s in (await db.execute(select(Subject).where(Subject.org_id == org))).scalars().all()}
    assessments_by_name = {a.name.strip().lower(): a for a in (await db.execute(
        select(Assessment).where(Assessment.org_id == org, Assessment.term_id == term_id))).scalars().all()}

    # Preload existing scores for this term's assessments to upsert in place.
    a_ids = [a.id for a in assessments_by_name.values()]
    existing: dict[tuple, object] = {}
    if a_ids:
        for r in (await db.execute(select(StudentAssessmentScore).where(
                StudentAssessmentScore.org_id == org, StudentAssessmentScore.assessment_id.in_(a_ids)))).scalars().all():
            existing[(r.student_id, r.subject_id, r.assessment_id)] = r

    imported = 0
    errors: list[str] = []
    for i, raw in enumerate(parsed, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        adm = (row.get("admission_no") or row.get("admission") or row.get("admission no") or "").lower()
        name = (row.get("student") or row.get("name") or row.get("student name") or "").lower()
        student = (by_adm.get(adm) if adm else None) or (by_name.get(name) if name else None)
        if not student:
            errors.append(f"row {i}: student not found ({row.get('student') or row.get('admission_no') or '—'})")
            continue
        subj = subjects_by_name.get((row.get("subject") or "").lower())
        if not subj:
            errors.append(f"row {i}: subject not found ({row.get('subject') or '—'})")
            continue
        wrote_any = False
        for col, val in row.items():
            if col in _UPLOAD_SKIP_COLS or val == "":
                continue
            a = assessments_by_name.get(col)
            if not a:
                continue
            try:
                score = Decimal(val)
            except (InvalidOperation, ValueError):
                errors.append(f"row {i}: '{val}' is not a number for {a.name}")
                continue
            key = (student.id, subj.id, a.id)
            row_obj = existing.get(key)
            if row_obj:
                row_obj.score = score
                row_obj.recorded_by = current_user.id
            else:
                new = StudentAssessmentScore(org_id=org, student_id=student.id, subject_id=subj.id,
                                             assessment_id=a.id, score=score, recorded_by=current_user.id)
                db.add(new)
                existing[key] = new
            wrote_any = True
        if wrote_any:
            imported += 1
        elif not any(assessments_by_name.get(c) for c in row):
            errors.append(f"row {i}: no matching assessment columns")
    await db.flush()
    return ScoreUploadResult(rows=len(parsed), imported=imported, errors=errors[:50])
