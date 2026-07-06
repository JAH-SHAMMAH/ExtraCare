from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog, AuditAction
from app.models.user import User


import decimal
import enum
import uuid
from datetime import date, datetime


async def log_action(
    db: AsyncSession,
    action: AuditAction,
    org_id: str,
    actor: User | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    resource_label: str | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    request: Request | None = None,
    severity: str = "info",
    metadata: dict | None = None,
):
    """
    Write an immutable audit log entry.
    Call after any significant state change.
    """

    def _make_jsonable(obj):
        if obj is None:
            return None
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        # Enum (incl. str-enums) → its value; date/datetime → ISO; UUID → str.
        # Keeps diff payloads JSON-serialisable when a changed field is a date
        # (hire_date, date_of_birth, lesson_date) or an enum status.
        if isinstance(obj, enum.Enum):
            return obj.value
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, dict):
            return {k: _make_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return [_make_jsonable(v) for v in obj]
        return obj

    metadata_safe = _make_jsonable(metadata or {})

    log = AuditLog(
        action=action,
        org_id=org_id,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_label=resource_label,
        old_values=_make_jsonable(old_values) if old_values is not None else None,
        new_values=_make_jsonable(new_values) if new_values is not None else None,
        severity=severity,
        metadata_=metadata_safe,
    )

    if request:
        # Extract IP (handles X-Forwarded-For for proxied deployments)
        forwarded_for = request.headers.get("X-Forwarded-For")
        log.actor_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host
        log.user_agent = request.headers.get("User-Agent", "")[:500]

    db.add(log)
    # Don't commit here — caller's transaction handles commit
