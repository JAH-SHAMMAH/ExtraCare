"""
Branding & Logo Management Routes
==================================

Organization admins can:
- Upload logos and favicons
- Configure branding colors
- Customize branding settings
- Retrieve branding configuration

Only org admins can modify branding.
Uploads are validated and optimized for web.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from app.deps import get_current_active_user
from app.models.organization import Organization
from app.models.user import User
from app.core.permissions import require_permission
from app.schemas.branding import (
    BrandingUpdateRequest,
    BrandingResponse,
    BrandingUploadResponse,
)
from app.services.branding_service import get_branding_service
from app.services.audit_service import log_action
from app.models.audit import AuditAction

_logger = logging.getLogger("extracare.branding")

router = APIRouter(prefix="/branding", tags=["Branding"])

# Only org admins can manage branding
_require_branding_admin = require_permission("organization:branding")


@router.get("/config")
async def get_branding_config(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BrandingResponse:
    """Get organization branding configuration."""
    org = await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = org.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return BrandingResponse(
        org_id=org.id,
        org_name=org.name,
        logo_url=org.logo_url,
        favicon_url=org.favicon_url,
        primary_color=org.primary_color,
        secondary_color=org.secondary_color,
        branding_settings=org.branding_settings or {},
    )


@router.post("/logo/upload", dependencies=[_require_branding_admin])
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BrandingUploadResponse:
    """Upload organization logo."""
    branding_svc = get_branding_service()

    # Validate and upload
    success, result, url = await branding_svc.upload_logo(current_user.org_id, file)

    if not success:
        _logger.warning(
            "branding.logo_upload_failed org_id=%s actor=%s error=%s",
            current_user.org_id, current_user.id, result
        )
        raise HTTPException(status_code=400, detail=result)

    # Update organization
    await db.execute(
        update(Organization)
        .where(Organization.id == current_user.org_id)
        .values(logo_url=url)
    )
    await db.commit()

    # Audit
    await log_action(
        db=db,
        org_id=current_user.org_id,
        action=AuditAction.UPDATE,
        actor=current_user,
        resource_type="organization_branding",
        resource_id=current_user.org_id,
        metadata={"field": "logo", "filename": result},
    )

    _logger.info(
        "branding.logo_uploaded org_id=%s actor=%s filename=%s",
        current_user.org_id, current_user.id, result
    )

    return BrandingUploadResponse(
        field="logo",
        url=url,
        filename=result,
        size_bytes=file.size or 0,
    )


@router.post("/favicon/upload", dependencies=[_require_branding_admin])
async def upload_favicon(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BrandingUploadResponse:
    """Upload organization favicon."""
    branding_svc = get_branding_service()

    # Validate and upload
    success, result, url = await branding_svc.upload_favicon(current_user.org_id, file)

    if not success:
        _logger.warning(
            "branding.favicon_upload_failed org_id=%s actor=%s error=%s",
            current_user.org_id, current_user.id, result
        )
        raise HTTPException(status_code=400, detail=result)

    # Update organization
    await db.execute(
        update(Organization)
        .where(Organization.id == current_user.org_id)
        .values(favicon_url=url)
    )
    await db.commit()

    # Audit
    await log_action(
        db=db,
        org_id=current_user.org_id,
        action=AuditAction.UPDATE,
        actor=current_user,
        resource_type="organization_branding",
        resource_id=current_user.org_id,
        metadata={"field": "favicon", "filename": result},
    )

    _logger.info(
        "branding.favicon_uploaded org_id=%s actor=%s filename=%s",
        current_user.org_id, current_user.id, result
    )

    return BrandingUploadResponse(
        field="favicon",
        url=url,
        filename=result,
        size_bytes=file.size or 0,
    )


@router.put("/update", dependencies=[_require_branding_admin])
async def update_branding(
    request: BrandingUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BrandingResponse:
    """Update organization branding colors and settings."""
    # Build update values
    update_values = {}

    if request.primary_color:
        # Validate hex color
        if not _is_valid_hex_color(request.primary_color):
            raise HTTPException(status_code=400, detail="Invalid primary color (must be hex, e.g. #16a34a)")
        update_values["primary_color"] = request.primary_color

    if request.secondary_color:
        if not _is_valid_hex_color(request.secondary_color):
            raise HTTPException(status_code=400, detail="Invalid secondary color (must be hex)")
        update_values["secondary_color"] = request.secondary_color

    if request.branding_settings:
        update_values["branding_settings"] = request.branding_settings.model_dump()

    if not update_values:
        raise HTTPException(status_code=400, detail="No branding fields to update")

    # Update organization
    await db.execute(
        update(Organization)
        .where(Organization.id == current_user.org_id)
        .values(**update_values)
    )
    await db.commit()

    # Audit
    await log_action(
        db=db,
        org_id=current_user.org_id,
        action=AuditAction.UPDATE,
        actor=current_user,
        resource_type="organization_branding",
        resource_id=current_user.org_id,
        metadata={"fields_updated": list(update_values.keys())},
    )

    _logger.info(
        "branding.updated org_id=%s actor=%s fields=%s",
        current_user.org_id, current_user.id, list(update_values.keys())
    )

    # Return updated config
    org = await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = org.scalar_one()

    return BrandingResponse(
        org_id=org.id,
        org_name=org.name,
        logo_url=org.logo_url,
        favicon_url=org.favicon_url,
        primary_color=org.primary_color,
        secondary_color=org.secondary_color,
        branding_settings=org.branding_settings or {},
    )


def _is_valid_hex_color(color: str) -> bool:
    """Validate hex color code."""
    import re
    return bool(re.match(r"^#[0-9a-fA-F]{6}$", color))
