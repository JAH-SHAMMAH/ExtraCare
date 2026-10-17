"""
Platform admin endpoints. Everything here is super-admin only and meant
for operational diagnostics, not tenant-facing features.
"""

import os
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.core.permissions import require_superadmin
from app.core.ratelimit import rate_limit_auth
from app.core.security import verify_password
from app.database import engine, get_db
from app.deps import get_current_active_user
from app.models.audit import AuditAction
from app.services.audit_service import log_action
from app.services.db_backup import dump_database
from app.core.tenant import denial_counters_snapshot
from app.models.user import User


router = APIRouter(prefix="/admin", tags=["Admin (Platform)"])


@router.get("/metrics", summary="In-process denial counters (super-admin only)")
async def get_metrics(_: User = Depends(require_superadmin)):
    """
    Snapshot of `module_access_denied` and `role_permission_denied` counts
    since the app booted. Surfaces the noisy tenants first, which is what
    we actually want when diagnosing 'nobody in org X can use feature Y'.
    """
    counters = denial_counters_snapshot()
    totals: dict[str, int] = {}
    for row in counters:
        totals[row["event"]] = totals.get(row["event"], 0) + row["count"]
    return {"totals": totals, "by_bucket": counters}


class BackupRequest(BaseModel):
    password: str


@router.post(
    "/backup/download",
    summary="Download a full database backup (Director / super-admin, password re-entry)",
    dependencies=[Depends(rate_limit_auth("db_backup"))],
)
async def download_backup(
    body: BackupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Only the top account: a platform super-admin or the holder of the "*"
    # (everything) permission. Ordinary admins are refused — the file contains
    # every student, staff and finance record.
    if not (current_user.is_superadmin or "*" in current_user.permissions):
        raise HTTPException(status_code=403, detail="Only the Director account can download a backup.")
    if not current_user.hashed_password or not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(status_code=403, detail="Wrong password.")

    fd, path = tempfile.mkstemp(prefix="fairview-backup-", suffix=".jsonl.gz")
    os.close(fd)
    try:
        counts = await dump_database(engine, __import__("pathlib").Path(path))
    except Exception:
        os.unlink(path)
        raise HTTPException(status_code=500, detail="The backup could not be produced. Nothing was changed.")

    await log_action(
        db, AuditAction.DATA_EXPORTED, org_id=current_user.org_id, actor=current_user,
        resource_type="database", resource_label="full database backup",
        metadata={"tables": len(counts), "rows": sum(counts.values())},
        request=request, severity="warning",
    )
    await db.commit()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return FileResponse(
        path, media_type="application/gzip",
        filename=f"fairview-backup-{stamp}.logical.jsonl.gz",
        background=BackgroundTask(os.unlink, path),
        headers={"Cache-Control": "no-store"},
    )
