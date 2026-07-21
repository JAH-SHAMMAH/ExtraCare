"""Training router (HR), prefix ``/hr``.

Training programs and their scheduled sessions. Confidential HR admin — gated
``hr:write``. Categories are the generic ``training_category`` managed list.

ENDPOINTS:
  GET/POST   /hr/trainings                  · PATCH/DELETE /hr/trainings/{id}
  GET/POST   /hr/trainings/{id}/sessions
  GET        /hr/training-sessions          (all sessions, with training title)
  PATCH/DELETE /hr/training-sessions/{id}
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.hr_training import Training, TrainingSession
from app.schemas.hr_training import (
    TrainingCreate, TrainingUpdate, TrainingResponse,
    SessionCreate, SessionUpdate, SessionResponse,
)

router = APIRouter(prefix="/hr", tags=["HR — Training"])

_can_hr = Depends(PermissionChecker("hr:write"))


def _t_response(t: Training, session_count: int = 0) -> TrainingResponse:
    return TrainingResponse(
        id=t.id, title=t.title, description=t.description, category=t.category,
        status=t.status, session_count=session_count, created_at=t.created_at, org_id=t.org_id,
    )


def _s_response(s: TrainingSession, training_title: str | None = None) -> SessionResponse:
    return SessionResponse(
        id=s.id, training_id=s.training_id, training_title=training_title, title=s.title,
        session_date=s.session_date, start_time=s.start_time, location=s.location,
        facilitator=s.facilitator, created_at=s.created_at, org_id=s.org_id,
    )


async def _get_training(db: AsyncSession, org_id: str, tid: str) -> Training:
    t = (await db.execute(select(Training).where(
        Training.id == tid, Training.org_id == org_id, Training.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Training not found.")
    return t


# ── Trainings ─────────────────────────────────────────────────────────────────

@router.get("/trainings", response_model=list[TrainingResponse], dependencies=[_can_hr])
async def list_trainings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(Training).where(Training.org_id == current_user.org_id, Training.is_deleted == False)  # noqa: E712
        .order_by(Training.created_at.desc())
    )).scalars().all()
    counts = dict((tid, c) for tid, c in (await db.execute(
        select(TrainingSession.training_id, func.count(TrainingSession.id)).where(
            TrainingSession.org_id == current_user.org_id, TrainingSession.is_deleted == False  # noqa: E712
        ).group_by(TrainingSession.training_id)
    )).all())
    return [_t_response(t, counts.get(t.id, 0)) for t in rows]


@router.post("/trainings", response_model=TrainingResponse, status_code=201, dependencies=[_can_hr])
async def create_training(payload: TrainingCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = Training(title=payload.title.strip(), description=(payload.description or None),
                 category=(payload.category or None), status=payload.status, org_id=current_user.org_id)
    db.add(t)
    await db.flush()
    return _t_response(t, 0)


@router.patch("/trainings/{tid}", response_model=TrainingResponse, dependencies=[_can_hr])
async def update_training(tid: str, payload: TrainingUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = await _get_training(db, current_user.org_id, tid)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        data["title"] = data["title"].strip()
    for f, v in data.items():
        setattr(t, f, v)
    await db.flush()
    cnt = (await db.execute(select(func.count(TrainingSession.id)).where(TrainingSession.training_id == t.id, TrainingSession.is_deleted == False))).scalar() or 0  # noqa: E712
    return _t_response(t, cnt)


@router.delete("/trainings/{tid}", status_code=204, dependencies=[_can_hr])
async def delete_training(tid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = await _get_training(db, current_user.org_id, tid)
    now = datetime.now(timezone.utc)
    t.is_deleted = True
    t.deleted_at = now
    # Soft-delete its sessions too, so they don't linger orphaned.
    sessions = (await db.execute(select(TrainingSession).where(
        TrainingSession.training_id == t.id, TrainingSession.is_deleted == False  # noqa: E712
    ))).scalars().all()
    for s in sessions:
        s.is_deleted = True
        s.deleted_at = now
    await db.flush()


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/trainings/{tid}/sessions", response_model=list[SessionResponse], dependencies=[_can_hr])
async def list_training_sessions(tid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = await _get_training(db, current_user.org_id, tid)
    rows = (await db.execute(
        select(TrainingSession).where(TrainingSession.training_id == t.id, TrainingSession.is_deleted == False)  # noqa: E712
        .order_by(TrainingSession.session_date.is_(None), TrainingSession.session_date)
    )).scalars().all()
    return [_s_response(s, t.title) for s in rows]


@router.post("/trainings/{tid}/sessions", response_model=SessionResponse, status_code=201, dependencies=[_can_hr])
async def create_session(tid: str, payload: SessionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = await _get_training(db, current_user.org_id, tid)
    s = TrainingSession(
        training_id=t.id, title=(payload.title or None), session_date=payload.session_date,
        start_time=payload.start_time, location=(payload.location or None),
        facilitator=(payload.facilitator or None), org_id=current_user.org_id,
    )
    db.add(s)
    await db.flush()
    return _s_response(s, t.title)


@router.get("/training-sessions", response_model=list[SessionResponse], dependencies=[_can_hr])
async def list_all_sessions(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(TrainingSession, Training.title).join(Training, Training.id == TrainingSession.training_id)
        .where(TrainingSession.org_id == current_user.org_id, TrainingSession.is_deleted == False,  # noqa: E712
               Training.is_deleted == False)  # noqa: E712
        .order_by(TrainingSession.session_date.is_(None), TrainingSession.session_date)
    )).all()
    return [_s_response(s, title) for s, title in rows]


async def _get_session(db: AsyncSession, org_id: str, sid: str) -> TrainingSession:
    s = (await db.execute(select(TrainingSession).where(
        TrainingSession.id == sid, TrainingSession.org_id == org_id, TrainingSession.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found.")
    return s


@router.patch("/training-sessions/{sid}", response_model=SessionResponse, dependencies=[_can_hr])
async def update_session(sid: str, payload: SessionUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, f, v)
    await db.flush()
    return _s_response(s)


@router.delete("/training-sessions/{sid}", status_code=204, dependencies=[_can_hr])
async def delete_session(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    s.is_deleted = True
    s.deleted_at = datetime.now(timezone.utc)
    await db.flush()
