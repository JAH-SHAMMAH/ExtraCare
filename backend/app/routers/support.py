"""Support router (NEW) — server-side contact form.

``POST /support`` always PERSISTS a SupportRequest (so nothing is lost) and then
makes a best-effort SMTP send to ``settings.SUPPORT_EMAIL``. Email failure never
fails the request; the row records whether the email went out.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.config import get_settings
from app.models.user import User
from app.models.support import SupportRequest
from app.services.email import send_email

router = APIRouter(prefix="/support", tags=["Support"])


class SupportRequestCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1)


class SupportRequestResponse(BaseModel):
    id: str
    subject: str
    message: str
    name: str | None
    email: str | None
    emailed: bool
    status: str
    created_at: datetime
    org_id: str


@router.post("", response_model=SupportRequestResponse, status_code=201)
async def create_support_request(
    payload: SupportRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sr = SupportRequest(
        user_id=current_user.id,
        name=current_user.full_name,
        email=current_user.email,
        subject=payload.subject.strip(),
        message=payload.message.strip(),
        org_id=current_user.org_id,
    )
    db.add(sr)
    await db.flush()

    body = (
        f"{payload.message}\n\n"
        f"—\nFrom: {current_user.full_name} <{current_user.email}>\n"
        f"User ID: {current_user.id}\nOrg ID: {current_user.org_id}"
    )
    sent = await run_in_threadpool(
        send_email,
        get_settings().SUPPORT_EMAIL,
        f"[Fairview Support] {payload.subject.strip()}",
        body,
        current_user.email,
    )
    sr.emailed = sent
    await db.commit()
    await db.refresh(sr)
    return sr


@router.get("", response_model=list[SupportRequestResponse], dependencies=[Depends(PermissionChecker("settings:read"))])
async def list_support_requests(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(SupportRequest).where(SupportRequest.org_id == current_user.org_id)
    if status:
        q = q.where(SupportRequest.status == status)
    rows = (await db.execute(q.order_by(SupportRequest.created_at.desc()))).scalars().all()
    return rows
