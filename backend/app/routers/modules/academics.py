"""Academic Records & Recognition router (Batch 3), prefix ``/academics``.

  /academics/subject-selections          GET/POST          school:subjects:*
  /academics/subject-selections/{id}     PATCH/DELETE
  /academics/transcripts                 GET/POST          school:grades:*
  /academics/transcripts/{id}            GET/PATCH/DELETE
  /academics/transcripts/{id}/entries    POST
  /academics/transcripts/{id}/entries/{entry_id}  DELETE
  /academics/report-workflow             GET/POST/…        school:reports:write
  /academics/recognitions                GET/POST          school:behaviour:*
  /academics/recognitions/{id}           PATCH/DELETE
  /academics/recognitions/leaderboard    GET               (house conduct totals)

Report-workflow uses ``school:reports:write`` (not :read) on purpose — students/
parents hold reports:read for their own report card, so write keeps the admin
approval tool staff-only. Every query is pinned to ``current_user.org_id``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.modules.school import Student, Subject, SchoolClass
from app.models.modules.academics import (
    SubjectSelection, Transcript, TranscriptEntry, ReportApproval, Recognition,
)
from app.schemas.academics import (
    SubjectSelectionCreate, SubjectSelectionUpdate, SubjectSelectionResponse, SubjectSelectionListResponse,
    TranscriptCreate, TranscriptUpdate, TranscriptResponse, TranscriptListResponse,
    TranscriptEntryCreate, TranscriptEntryResponse,
    ReportApprovalCreate, ReportApprovalUpdate, ReportApprovalResponse, ReportApprovalListResponse,
    RecognitionCreate, RecognitionUpdate, RecognitionResponse, RecognitionListResponse,
    HouseLeaderboardRow, LeaderboardResponse,
    SELECTION_STATUSES, TRANSCRIPT_STATUSES, REPORT_STAGES, RECOGNITION_TYPES, AWARD_TYPES,
)
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(
    prefix="/academics",
    tags=["Academic Records & Recognition"],
    dependencies=[Depends(require_role_module("school"))],
)

_subj_read = Depends(PermissionChecker("school:subjects:read"))
_subj_write = Depends(PermissionChecker("school:subjects:write"))
_grade_read = Depends(PermissionChecker("school:grades:read"))
_grade_write = Depends(PermissionChecker("school:grades:write"))
_report_write = Depends(PermissionChecker("school:reports:write"))
_beh_read = Depends(PermissionChecker("school:behaviour:read"))
_beh_write = Depends(PermissionChecker("school:behaviour:write"))


# ── name resolution helpers ───────────────────────────────────────────────────

async def _student_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Student.id, Student.first_name, Student.last_name).where(
            Student.org_id == org_id, Student.id.in_(ids))
    )).all()
    return {r.id: f"{r.first_name} {r.last_name}".strip() for r in rows}


async def _subject_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Subject.id, Subject.name).where(Subject.org_id == org_id, Subject.id.in_(ids))
    )).all()
    return {r.id: r.name for r in rows}


async def _class_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(SchoolClass.id, SchoolClass.name).where(SchoolClass.org_id == org_id, SchoolClass.id.in_(ids))
    )).all()
    return {r.id: r.name for r in rows}


async def _require_student(db: AsyncSession, org_id: str, student_id: str) -> Student:
    s = (await db.execute(
        select(Student).where(
            Student.id == student_id, Student.org_id == org_id, Student.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="student not found in your organisation.")
    return s


# ── Subject Selection ──────────────────────────────────────────────────────────

def _selection_response(s: SubjectSelection, sname: str | None, subj: str | None) -> SubjectSelectionResponse:
    return SubjectSelectionResponse(
        id=s.id, student_id=s.student_id, student_name=sname,
        subject_id=s.subject_id, subject_name=subj,
        academic_year=s.academic_year, term=s.term, status=s.status,
        created_at=s.created_at, org_id=s.org_id,
    )


@router.get("/subject-selections", response_model=SubjectSelectionListResponse, dependencies=[_subj_read])
async def list_subject_selections(
    student_id: str | None = Query(default=None),
    subject_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(SubjectSelection).where(SubjectSelection.org_id == current_user.org_id)
    if student_id:
        base = base.where(SubjectSelection.student_id == student_id)
    if subject_id:
        base = base.where(SubjectSelection.subject_id == subject_id)
    if status:
        base = base.where(SubjectSelection.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(SubjectSelection.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    subj = await _subject_names(db, current_user.org_id, {r.subject_id for r in rows})
    return SubjectSelectionListResponse(
        items=[_selection_response(r, snames.get(r.student_id), subj.get(r.subject_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/subject-selections", response_model=SubjectSelectionResponse, status_code=201, dependencies=[_subj_write])
async def create_subject_selection(
    payload: SubjectSelectionCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.status not in SELECTION_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(SELECTION_STATUSES)}")
    student = await _require_student(db, current_user.org_id, payload.student_id)
    subject = (await db.execute(
        select(Subject).where(Subject.id == payload.subject_id, Subject.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="subject not found in your organisation.")
    sel = SubjectSelection(
        student_id=student.id, subject_id=subject.id, academic_year=payload.academic_year,
        term=payload.term, status=payload.status, selected_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(sel)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That subject is already selected for the student this year.")
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="SubjectSelection", resource_id=sel.id,
        resource_label=f"subject selection {subject.name}", request=request,
    )
    return _selection_response(sel, f"{student.first_name} {student.last_name}".strip(), subject.name)


@router.patch("/subject-selections/{selection_id}", response_model=SubjectSelectionResponse, dependencies=[_subj_write])
async def update_subject_selection(
    selection_id: str,
    payload: SubjectSelectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sel = (await db.execute(
        select(SubjectSelection).where(
            SubjectSelection.id == selection_id, SubjectSelection.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not sel:
        raise HTTPException(status_code=404, detail="Selection not found.")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in SELECTION_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(SELECTION_STATUSES)}")
    for field, value in data.items():
        setattr(sel, field, value)
    await db.flush()
    snames = await _student_names(db, current_user.org_id, {sel.student_id})
    subj = await _subject_names(db, current_user.org_id, {sel.subject_id})
    return _selection_response(sel, snames.get(sel.student_id), subj.get(sel.subject_id))


@router.delete("/subject-selections/{selection_id}", status_code=204, dependencies=[_subj_write])
async def delete_subject_selection(
    selection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sel = (await db.execute(
        select(SubjectSelection).where(
            SubjectSelection.id == selection_id, SubjectSelection.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not sel:
        raise HTTPException(status_code=404, detail="Selection not found.")
    await db.delete(sel)


# ── Transcripts (Mark Books & Transcripts) ──────────────────────────────────────

def _avg(entries: list[TranscriptEntry]) -> float | None:
    scores = [e.score for e in entries if e.score is not None]
    return round(sum(scores) / len(scores), 2) if scores else None


def _transcript_response(t: Transcript, entries: list[TranscriptEntry], sname: str | None) -> TranscriptResponse:
    return TranscriptResponse(
        id=t.id, student_id=t.student_id, student_name=sname,
        academic_year=t.academic_year, term=t.term, average=t.average, remark=t.remark, status=t.status,
        entries=[TranscriptEntryResponse(id=e.id, subject_name=e.subject_name, score=e.score, grade=e.grade, remark=e.remark) for e in entries],
        created_at=t.created_at, org_id=t.org_id,
    )


async def _load_transcript(db: AsyncSession, tid: str, org_id: str) -> Transcript:
    t = (await db.execute(
        select(Transcript).where(
            Transcript.id == tid, Transcript.org_id == org_id, Transcript.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return t


async def _entries_for(db: AsyncSession, transcript_ids: list[str]) -> dict[str, list[TranscriptEntry]]:
    if not transcript_ids:
        return {}
    rows = (await db.execute(
        select(TranscriptEntry).where(TranscriptEntry.transcript_id.in_(transcript_ids))
        .order_by(TranscriptEntry.subject_name)
    )).scalars().all()
    out: dict[str, list[TranscriptEntry]] = {}
    for e in rows:
        out.setdefault(e.transcript_id, []).append(e)
    return out


@router.get("/transcripts", response_model=TranscriptListResponse, dependencies=[_grade_read])
async def list_transcripts(
    student_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(Transcript).where(
        Transcript.org_id == current_user.org_id, Transcript.is_deleted == False)  # noqa: E712
    if student_id:
        base = base.where(Transcript.student_id == student_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(Transcript.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    entries = await _entries_for(db, [r.id for r in rows])
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return TranscriptListResponse(
        items=[_transcript_response(r, entries.get(r.id, []), snames.get(r.student_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/transcripts", response_model=TranscriptResponse, status_code=201, dependencies=[_grade_write])
async def create_transcript(
    payload: TranscriptCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    student = await _require_student(db, current_user.org_id, payload.student_id)
    t = Transcript(
        student_id=student.id, academic_year=payload.academic_year, term=payload.term,
        remark=payload.remark, status="draft", org_id=current_user.org_id,
    )
    db.add(t)
    await db.flush()
    entries = [
        TranscriptEntry(transcript_id=t.id, subject_name=e.subject_name, score=e.score,
                        grade=e.grade, remark=e.remark, org_id=current_user.org_id)
        for e in payload.entries
    ]
    for e in entries:
        db.add(e)
    t.average = _avg(entries)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="Transcript", resource_id=t.id,
        resource_label=f"transcript for {student.first_name} {student.last_name}", request=request,
    )
    return _transcript_response(t, entries, f"{student.first_name} {student.last_name}".strip())


@router.get("/transcripts/{transcript_id}", response_model=TranscriptResponse, dependencies=[_grade_read])
async def get_transcript(
    transcript_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    t = await _load_transcript(db, transcript_id, current_user.org_id)
    entries = (await _entries_for(db, [t.id])).get(t.id, [])
    snames = await _student_names(db, current_user.org_id, {t.student_id})
    return _transcript_response(t, entries, snames.get(t.student_id))


@router.patch("/transcripts/{transcript_id}", response_model=TranscriptResponse, dependencies=[_grade_write])
async def update_transcript(
    transcript_id: str,
    payload: TranscriptUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    t = await _load_transcript(db, transcript_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in TRANSCRIPT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(TRANSCRIPT_STATUSES)}")
    if "status" in data and data["status"] == "issued":
        t.issued_by = current_user.id
    for field, value in data.items():
        setattr(t, field, value)
    await db.flush()
    entries = (await _entries_for(db, [t.id])).get(t.id, [])
    snames = await _student_names(db, current_user.org_id, {t.student_id})
    return _transcript_response(t, entries, snames.get(t.student_id))


@router.post("/transcripts/{transcript_id}/entries", response_model=TranscriptResponse, status_code=201, dependencies=[_grade_write])
async def add_transcript_entry(
    transcript_id: str,
    payload: TranscriptEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    t = await _load_transcript(db, transcript_id, current_user.org_id)
    db.add(TranscriptEntry(
        transcript_id=t.id, subject_name=payload.subject_name, score=payload.score,
        grade=payload.grade, remark=payload.remark, org_id=current_user.org_id,
    ))
    await db.flush()
    entries = (await _entries_for(db, [t.id])).get(t.id, [])
    t.average = _avg(entries)
    await db.flush()
    snames = await _student_names(db, current_user.org_id, {t.student_id})
    return _transcript_response(t, entries, snames.get(t.student_id))


@router.delete("/transcripts/{transcript_id}/entries/{entry_id}", response_model=TranscriptResponse, dependencies=[_grade_write])
async def delete_transcript_entry(
    transcript_id: str,
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    t = await _load_transcript(db, transcript_id, current_user.org_id)
    entry = (await db.execute(
        select(TranscriptEntry).where(
            TranscriptEntry.id == entry_id, TranscriptEntry.transcript_id == t.id,
            TranscriptEntry.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found.")
    await db.delete(entry)
    await db.flush()
    entries = (await _entries_for(db, [t.id])).get(t.id, [])
    t.average = _avg(entries)
    await db.flush()
    snames = await _student_names(db, current_user.org_id, {t.student_id})
    return _transcript_response(t, entries, snames.get(t.student_id))


@router.delete("/transcripts/{transcript_id}", status_code=204, dependencies=[_grade_write])
async def delete_transcript(
    transcript_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    t = await _load_transcript(db, transcript_id, current_user.org_id)
    t.is_deleted = True
    t.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Report Workflow ────────────────────────────────────────────────────────────

def _report_response(r: ReportApproval, cname: str | None) -> ReportApprovalResponse:
    return ReportApprovalResponse(
        id=r.id, class_id=r.class_id, class_name=cname, academic_year=r.academic_year,
        term=r.term, stage=r.stage, notes=r.notes,
        created_at=r.created_at, updated_at=r.updated_at, org_id=r.org_id,
    )


@router.get("/report-workflow", response_model=ReportApprovalListResponse, dependencies=[_report_write])
async def list_report_workflow(
    stage: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(ReportApproval).where(ReportApproval.org_id == current_user.org_id)
    if stage:
        base = base.where(ReportApproval.stage == stage)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(ReportApproval.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    cnames = await _class_names(db, current_user.org_id, {r.class_id for r in rows})
    return ReportApprovalListResponse(
        items=[_report_response(r, cnames.get(r.class_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/report-workflow", response_model=ReportApprovalResponse, status_code=201, dependencies=[_report_write])
async def create_report_workflow(
    payload: ReportApprovalCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.class_id:
        cls = (await db.execute(
            select(SchoolClass).where(SchoolClass.id == payload.class_id, SchoolClass.org_id == current_user.org_id)
        )).scalar_one_or_none()
        if not cls:
            raise HTTPException(status_code=404, detail="class not found in your organisation.")
    r = ReportApproval(
        class_id=payload.class_id, academic_year=payload.academic_year, term=payload.term,
        notes=payload.notes, stage="draft", org_id=current_user.org_id,
    )
    db.add(r)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="ReportApproval", resource_id=r.id, resource_label="report workflow", request=request,
    )
    cnames = await _class_names(db, current_user.org_id, {r.class_id})
    return _report_response(r, cnames.get(r.class_id))


@router.patch("/report-workflow/{workflow_id}", response_model=ReportApprovalResponse, dependencies=[_report_write])
async def update_report_workflow(
    workflow_id: str,
    payload: ReportApprovalUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = (await db.execute(
        select(ReportApproval).where(ReportApproval.id == workflow_id, ReportApproval.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    data = payload.model_dump(exclude_unset=True)
    if "stage" in data:
        if data["stage"] not in REPORT_STAGES:
            raise HTTPException(status_code=422, detail=f"stage must be one of {REPORT_STAGES}")
        old_stage, new_stage = r.stage, data["stage"]
        # Stamp the actor for the stage they moved it into.
        if new_stage == "submitted":
            r.submitted_by = current_user.id
        elif new_stage == "reviewed":
            r.reviewed_by = current_user.id
        elif new_stage == "approved":
            r.approved_by = current_user.id
        await log_action(
            db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
            resource_type="ReportApproval", resource_id=r.id, resource_label="report workflow stage",
            old_values={"stage": old_stage}, new_values={"stage": new_stage}, request=request,
        )
    for field, value in data.items():
        setattr(r, field, value)
    await db.flush()
    cnames = await _class_names(db, current_user.org_id, {r.class_id})
    return _report_response(r, cnames.get(r.class_id))


@router.delete("/report-workflow/{workflow_id}", status_code=204, dependencies=[_report_write])
async def delete_report_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = (await db.execute(
        select(ReportApproval).where(ReportApproval.id == workflow_id, ReportApproval.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    await db.delete(r)


# ── Merit & Awards (Recognition) ────────────────────────────────────────────────

def _recognition_response(r: Recognition, sname: str | None) -> RecognitionResponse:
    return RecognitionResponse(
        id=r.id, type=r.type, student_id=r.student_id, student_name=sname,
        title=r.title, reason=r.reason, points=r.points, house=r.house, category=r.category,
        award_type=r.award_type, term=r.term, awarded_on=r.awarded_on,
        created_at=r.created_at, org_id=r.org_id,
    )


@router.get("/recognitions/leaderboard", response_model=LeaderboardResponse, dependencies=[_beh_read])
async def recognition_leaderboard(
    term: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """House conduct-point totals (type=conduct_point), highest first."""
    q = select(
        Recognition.house,
        func.coalesce(func.sum(Recognition.points), 0).label("total"),
        func.count(Recognition.id).label("entries"),
    ).where(
        Recognition.org_id == current_user.org_id,
        Recognition.type == "conduct_point",
        Recognition.house.isnot(None),
    )
    if term:
        q = q.where(Recognition.term == term)
    rows = (await db.execute(q.group_by(Recognition.house).order_by(func.sum(Recognition.points).desc()))).all()
    return LeaderboardResponse(
        houses=[HouseLeaderboardRow(house=r.house, total_points=int(r.total or 0), entries=r.entries) for r in rows],
    )


@router.get("/recognitions", response_model=RecognitionListResponse, dependencies=[_beh_read])
async def list_recognitions(
    type: str | None = Query(default=None),
    student_id: str | None = Query(default=None),
    house: str | None = Query(default=None),
    term: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(Recognition).where(Recognition.org_id == current_user.org_id)
    if type:
        base = base.where(Recognition.type == type)
    if student_id:
        base = base.where(Recognition.student_id == student_id)
    if house:
        base = base.where(Recognition.house == house)
    if term:
        base = base.where(Recognition.term == term)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(Recognition.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return RecognitionListResponse(
        items=[_recognition_response(r, snames.get(r.student_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/recognitions", response_model=RecognitionResponse, status_code=201, dependencies=[_beh_write])
async def create_recognition(
    payload: RecognitionCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.type not in RECOGNITION_TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {sorted(RECOGNITION_TYPES)}")
    if payload.type == "academic_award" and payload.award_type and payload.award_type not in AWARD_TYPES:
        raise HTTPException(status_code=422, detail=f"award_type must be one of {sorted(AWARD_TYPES)}")
    if payload.type == "conduct_point" and payload.points is None:
        raise HTTPException(status_code=422, detail="points is required for a conduct_point.")
    student = await _require_student(db, current_user.org_id, payload.student_id)
    r = Recognition(
        type=payload.type, student_id=student.id, title=payload.title, reason=payload.reason,
        points=payload.points, house=payload.house, category=payload.category,
        award_type=payload.award_type, term=payload.term, awarded_on=payload.awarded_on,
        recorded_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(r)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="Recognition", resource_id=r.id,
        resource_label=f"{payload.type} for student {student.id}",
        metadata={"type": payload.type, "points": payload.points}, request=request,
    )
    return _recognition_response(r, f"{student.first_name} {student.last_name}".strip())


@router.patch("/recognitions/{recognition_id}", response_model=RecognitionResponse, dependencies=[_beh_write])
async def update_recognition(
    recognition_id: str,
    payload: RecognitionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = (await db.execute(
        select(Recognition).where(Recognition.id == recognition_id, Recognition.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Recognition not found.")
    data = payload.model_dump(exclude_unset=True)
    if "award_type" in data and data["award_type"] and data["award_type"] not in AWARD_TYPES:
        raise HTTPException(status_code=422, detail=f"award_type must be one of {sorted(AWARD_TYPES)}")
    for field, value in data.items():
        setattr(r, field, value)
    await db.flush()
    snames = await _student_names(db, current_user.org_id, {r.student_id})
    return _recognition_response(r, snames.get(r.student_id))


@router.delete("/recognitions/{recognition_id}", status_code=204, dependencies=[_beh_write])
async def delete_recognition(
    recognition_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = (await db.execute(
        select(Recognition).where(Recognition.id == recognition_id, Recognition.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Recognition not found.")
    await db.delete(r)
