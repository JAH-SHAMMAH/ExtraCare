"""
Branding & Logo Upload Schemas
===============================

Schemas for organization branding configuration and logo uploads.
"""

from pydantic import BaseModel, HttpUrl
from typing import Optional


class BrandingSettingsSchema(BaseModel):
    """Organization branding configuration."""
    display_name: Optional[str] = None
    accent_color: Optional[str] = None
    font_family: Optional[str] = None
    description: Optional[str] = None


class BrandingUpdateRequest(BaseModel):
    """Request to update organization branding."""
    primary_color: Optional[str] = None  # Hex color code
    secondary_color: Optional[str] = None  # Hex color code
    branding_settings: Optional[BrandingSettingsSchema] = None


class BrandingResponse(BaseModel):
    """Response with organization branding info."""
    org_id: str
    org_name: str
    logo_url: Optional[str]
    favicon_url: Optional[str]
    primary_color: str
    secondary_color: str
    branding_settings: dict


class BrandingUploadResponse(BaseModel):
    """Response from logo/favicon upload."""
    field: str  # "logo" or "favicon"
    url: str
    filename: str
    size_bytes: int
