"""
Import History, Bulk Undo, and Background Processing endpoints.
Provides server-side import tracking per organization with rollback support
and async background processing for large CSV files (5k-50k rows).
"""
import asyncio
import time
from datetime import datetime, timezone, date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.database import get_db, AsyncSessionLocal
from app.deps import get_current_active_user
from app.models.user import User
from app.services.import_files import rows_from_upload
from app.models.import_job import ImportJob, ImportStatus
from app.models.modules.business import InventoryItem, FinanceTransaction, Employee, TransactionType
from app.models.modules.school import Student
from app.models.modules.hospital import Patient
from app.services.audit_service import log_action
from app.models.audit import AuditAction
from app.core.permissions import PermissionChecker
from app.core.ratelimit import rate_limit_auth

router = APIRouter(
    prefix="/imports",
    tags=["Import History"],
)

_can_read = Depends(PermissionChecker("imports:read"))
_can_write = Depends(PermissionChecker("imports:write"))
_can_rollback = Depends(PermissionChecker("imports:rollback"))

_PARSE_MAX_ROWS = 5000


@router.post("/parse-file", dependencies=[_can_write, Depends(rate_limit_auth("imports"))])
async def parse_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Parse an uploaded CSV / Excel (.xlsx) / Word (.docx) / PDF into
    ``{headers, rows}`` for the import wizard. Word/PDF must contain a table whose
    first row is the column headers. (CSV is still parsed in the browser; this
    endpoint serves the richer formats.) No data is written."""
    content = await file.read()
    try:
        rows = rows_from_upload(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not rows:
        raise HTTPException(status_code=422, detail="No rows found in the file.")
    if len(rows) > _PARSE_MAX_ROWS:
        raise HTTPException(status_code=422, detail=f"Too many rows. Maximum is {_PARSE_MAX_ROWS:,} per file.")
    headers = list(rows[0].keys())
    return {"headers": headers, "rows": rows, "warnings": []}


# ── Entity model map for undo ────────────────────────────────────────────────

ENTITY_MODELS = {
    "students": Student,
    "patients": Patient,
    "employees": Employee,
    "inventory": InventoryItem,
    "transactions": FinanceTransaction,
}


def _job_summary(job: ImportJob) -> dict:
    """Lightweight projection for list endpoints — omits heavy JSON columns
    (created_ids, error_details) so a 20-job page doesn't ship megabytes."""
    return {
        "id": job.id,
        "entity": job.entity,
        "filename": job.filename,
        "status": job.status.value,
        "total_rows": job.total_rows,
        "valid_rows": job.valid_rows,
        "created": job.created,
        "failed": job.failed,
        "skipped_invalid": job.skipped_invalid,
        "skipped_duplicate": job.skipped_duplicate,
        "duration_ms": job.duration_ms,
        "created_count": len(job.created_ids or []),
        "user_email": job.user_email,
        "duplicate_strategy": job.duplicate_strategy,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def _job_dict(job: ImportJob) -> dict:
    """Full projection including created_ids and error_details. Use for single-job endpoints."""
    return {
        **_job_summary(job),
        "created_ids": job.created_ids or [],
        "error_details": job.error_details or [],
    }


# Maximum IDs per IN clause (SQLite parameter limit is 999 by default)
MAX_IN_CLAUSE_SIZE = 500


# ── Create (called by frontend after import completes) ───────────────────────

@router.post("", status_code=201, dependencies=[_can_write, Depends(rate_limit_auth("imports"))])
async def create_import_job(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Record a completed import job."""
    entity = data.get("entity")
    if not entity:
        raise HTTPException(status_code=422, detail="entity is required")

    failed_count = data.get("failed", 0)
    created_count = data.get("created", 0)

    if failed_count > 0 and created_count > 0:
        status = ImportStatus.PARTIALLY_COMPLETED
    elif failed_count > 0 and created_count == 0:
        status = ImportStatus.FAILED
    else:
        status = ImportStatus.COMPLETED

    job = ImportJob(
        entity=entity,
        filename=data.get("filename", "unknown.csv"),
        status=status,
        total_rows=data.get("total_rows", 0),
        valid_rows=data.get("valid_rows", 0),
        created=created_count,
        failed=failed_count,
        skipped_invalid=data.get("skipped_invalid", 0),
        skipped_duplicate=data.get("skipped_duplicate", 0),
        duration_ms=data.get("duration_ms", 0),
        created_ids=data.get("created_ids", []),
        error_details=data.get("error_details", []),
        user_id=current_user.id,
        user_email=current_user.email,
        duplicate_strategy=data.get("duplicate_strategy", "skip"),
        org_id=current_user.org_id,
    )
    db.add(job)
    await db.flush()

    await log_action(
        db, AuditAction.DATA_IMPORTED, current_user.org_id,
        actor=current_user,
        resource_type="ImportJob",
        resource_id=job.id,
        resource_label=f"Import {entity}: {job.filename}",
        new_values={"created": created_count, "failed": failed_count, "entity": entity},
        severity="info",
    )

    return _job_dict(job)


# ── List (paginated, filterable by entity) ───────────────────────────────────

@router.get("", dependencies=[_can_read])
async def list_import_jobs(
    entity: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List import jobs for the current organization."""
    base_filter = [ImportJob.org_id == current_user.org_id]
    if entity:
        base_filter.append(ImportJob.entity == entity)

    total = (await db.execute(select(func.count(ImportJob.id)).where(*base_filter))).scalar()
    result = await db.execute(
        select(ImportJob)
        .where(*base_filter)
        .order_by(ImportJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = result.scalars().all()

    return {
        "items": [_job_summary(j) for j in jobs],
        "total": total,
        "page": page,
    }


# ── Get single job ───────────────────────────────────────────────────────────

@router.get("/{job_id}", dependencies=[_can_read])
async def get_import_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == job_id,
            ImportJob.org_id == current_user.org_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found.")
    return _job_dict(job)


# ── Rollback / Undo ─────────────────────────────────────────────────────────

@router.post("/{job_id}/rollback", status_code=200, dependencies=[_can_rollback, Depends(rate_limit_auth("imports"))])
async def rollback_import(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Soft-delete all records created by this import job.
    Only works for completed/partially_completed imports.
    """
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == job_id,
            ImportJob.org_id == current_user.org_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found.")

    if job.status == ImportStatus.ROLLED_BACK:
        raise HTTPException(status_code=400, detail="This import has already been rolled back.")

    if job.status not in (ImportStatus.COMPLETED, ImportStatus.PARTIALLY_COMPLETED):
        raise HTTPException(status_code=400, detail="Only completed imports can be rolled back.")

    created_ids = job.created_ids or []
    if not created_ids:
        raise HTTPException(status_code=400, detail="No records to roll back — created_ids is empty.")

    model = ENTITY_MODELS.get(job.entity)
    if not model:
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {job.entity}")
    if not hasattr(model, "is_deleted"):
        raise HTTPException(
            status_code=400,
            detail=f"Entity '{job.entity}' does not support soft-delete. Manual cleanup required.",
        )

    # Chunk to stay under SQLite's 999-parameter limit on IN clauses
    rolled_back = 0
    now = datetime.now(timezone.utc)
    for i in range(0, len(created_ids), MAX_IN_CLAUSE_SIZE):
        chunk = created_ids[i : i + MAX_IN_CLAUSE_SIZE]
        stmt = (
            update(model)
            .where(
                model.id.in_(chunk),
                model.org_id == current_user.org_id,
                model.is_deleted == False,
            )
            .values(is_deleted=True, deleted_at=now)
        )
        res = await db.execute(stmt)
        rolled_back += res.rowcount or 0

    job.status = ImportStatus.ROLLED_BACK

    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id,
        actor=current_user,
        resource_type="ImportJob",
        resource_id=job.id,
        resource_label=f"Rollback import {job.entity}: {job.filename}",
        new_values={"rolled_back": rolled_back, "entity": job.entity},
        severity="warning",
    )

    return {
        "rolled_back": rolled_back,
        "total_created": len(created_ids),
        "status": "rolled_back",
    }


# ── Duplicate check ──────────────────────────────────────────────────────────

@router.post("/check-duplicates", dependencies=[_can_write, Depends(rate_limit_auth("imports"))])
async def check_duplicates(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Check for existing records that would conflict with import data.
    Accepts { entity, field, values: string[] }.
    Returns { duplicates: string[] } — the values that already exist.
    """
    entity = data.get("entity")
    field = data.get("field")
    values = data.get("values", [])

    if not entity or not field or not values:
        raise HTTPException(status_code=422, detail="entity, field, and values are required")

    model = ENTITY_MODELS.get(entity)
    if not model:
        raise HTTPException(status_code=400, detail=f"Unknown entity: {entity}")

    col = getattr(model, field, None)
    if col is None:
        raise HTTPException(status_code=400, detail=f"Unknown field: {field}")

    # Build query for existing values
    query = select(col).where(
        model.org_id == current_user.org_id,
        col.in_(values),
    )

    # If model has soft delete, exclude deleted records
    if hasattr(model, "is_deleted"):
        query = query.where(model.is_deleted == False)

    result = await db.execute(query)
    existing = [str(r[0]) for r in result.all() if r[0] is not None]

    return {"duplicates": existing, "total": len(existing)}


# ── Background Processing ────────────────────────────────────────────────────

def _coerce_row_for_entity(entity: str, row: dict) -> dict:
    """Apply backend-side type coercion (dates, enums) for raw row data."""
    cleaned = {k: v for k, v in row.items() if v not in ("", None)}

    # Convert ISO date strings to date objects for known date fields
    DATE_FIELDS = {"date_of_birth", "hire_date", "transaction_date", "admission_date", "graduation_date"}
    for field in DATE_FIELDS:
        if field in cleaned and isinstance(cleaned[field], str):
            try:
                cleaned[field] = date.fromisoformat(cleaned[field])
            except ValueError:
                pass

    if entity == "transactions" and "type" in cleaned:
        try:
            cleaned["type"] = TransactionType(cleaned["type"])
        except ValueError:
            pass
        if "amount" in cleaned:
            try:
                cleaned["amount"] = float(cleaned["amount"])
            except (TypeError, ValueError):
                pass

    return cleaned


async def _process_background_import(job_id: str, org_id: str, entity: str, rows: list[dict]):
    """
    Background task that processes rows row-by-row in its own DB session.
    Updates the ImportJob with progress and final status.
    """
    model = ENTITY_MODELS.get(entity)
    if not model:
        return

    start = time.perf_counter()
    created_ids: list[str] = []
    failed: list[dict] = []
    created_count = 0

    async with AsyncSessionLocal() as session:
        for idx, row in enumerate(rows, start=1):
            try:
                cleaned = _coerce_row_for_entity(entity, row)
                cleaned.pop("org_id", None)  # Never let client override org
                instance = model(**cleaned, org_id=org_id)
                session.add(instance)
                await session.flush()
                created_ids.append(instance.id)
                created_count += 1
            except Exception as e:  # noqa: BLE001 — collect any backend error
                failed.append({"row": idx, "error": str(e)[:500], "data": row})
                await session.rollback()

            # Yield to event loop every 50 rows so other requests can run
            if idx % 50 == 0:
                await asyncio.sleep(0)

        # Commit all successful inserts
        try:
            await session.commit()
        except Exception:
            await session.rollback()

        # Update the ImportJob with final status
        duration_ms = int((time.perf_counter() - start) * 1000)
        job_result = await session.execute(select(ImportJob).where(ImportJob.id == job_id))
        job = job_result.scalar_one_or_none()
        if job:
            if failed and created_count > 0:
                job.status = ImportStatus.PARTIALLY_COMPLETED
            elif failed and created_count == 0:
                job.status = ImportStatus.FAILED
            else:
                job.status = ImportStatus.COMPLETED
            job.created = created_count
            job.failed = len(failed)
            job.created_ids = created_ids
            job.error_details = failed[:100]  # Cap at 100 stored errors
            job.duration_ms = duration_ms
            await session.commit()


@router.post("/background", status_code=202, dependencies=[_can_write, Depends(rate_limit_auth("imports"))])
async def start_background_import(
    data: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Start a background import job. Returns the job ID immediately;
    the frontend polls GET /imports/{id} for progress and final status.
    Use this for files larger than ~1000 rows.
    """
    entity = data.get("entity")
    rows = data.get("rows", [])

    if not entity:
        raise HTTPException(status_code=422, detail="entity is required")
    if entity not in ENTITY_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown entity: {entity}")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=422, detail="rows must be a non-empty list")
    if len(rows) > 50_000:
        raise HTTPException(status_code=413, detail="Maximum 50,000 rows per background import")

    # Create the job in 'processing' state
    job = ImportJob(
        entity=entity,
        filename=data.get("filename", "unknown.csv"),
        status=ImportStatus.PROCESSING,
        total_rows=len(rows),
        valid_rows=len(rows),
        created=0,
        failed=0,
        skipped_invalid=data.get("skipped_invalid", 0),
        skipped_duplicate=data.get("skipped_duplicate", 0),
        duration_ms=0,
        created_ids=[],
        error_details=[],
        user_id=current_user.id,
        user_email=current_user.email,
        duplicate_strategy=data.get("duplicate_strategy", "skip"),
        org_id=current_user.org_id,
    )
    db.add(job)
    await db.flush()

    # Capture values needed by background task before the request transaction closes
    job_id = job.id
    org_id = current_user.org_id

    background_tasks.add_task(_process_background_import, job_id, org_id, entity, rows)

    await log_action(
        db, AuditAction.DATA_IMPORTED, current_user.org_id,
        actor=current_user,
        resource_type="ImportJob",
        resource_id=job_id,
        resource_label=f"Background import {entity}: {job.filename}",
        new_values={"total_rows": len(rows), "entity": entity, "mode": "background"},
        severity="info",
    )

    return _job_dict(job)