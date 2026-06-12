"""
Branding Service
================

Handle organization logo uploads, branding configuration, and asset management.

Security considerations:
- Only org admins can upload/modify branding
- File size limits enforced
- Image validation (MIME type, dimensions)
- Sanitized filenames
- Secure storage paths (isolated by org_id)
"""

import os
import logging
from pathlib import Path
from typing import Optional
from io import BytesIO

# from PIL import Image
from fastapi import UploadFile

_logger = logging.getLogger("extracare.branding_service")


class BrandingService:
    """Handle branding asset uploads and configuration."""

    # Configuration
    MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}
    DEFAULT_LOGO_WIDTH = 400
    DEFAULT_LOGO_HEIGHT = 200
    
    def __init__(self, upload_base_dir: Optional[str] = None):
        """Initialize branding service."""
        self.upload_base_dir = upload_base_dir or os.path.join(os.getcwd(), "uploads")
        Path(self.upload_base_dir).mkdir(parents=True, exist_ok=True)
        _logger.info("branding_service.initialized upload_dir=%s", self.upload_base_dir)

    def _get_org_upload_dir(self, org_id: str) -> str:
        """Get isolated upload directory for an organization."""
        org_dir = os.path.join(self.upload_base_dir, org_id, "branding")
        Path(org_dir).mkdir(parents=True, exist_ok=True)
        return org_dir

    def _sanitize_filename(self, filename: str, prefix: str = "") -> str:
        """Sanitize and prefix filename for security."""
        # Remove path components
        filename = os.path.basename(filename)
        # Get extension
        _, ext = os.path.splitext(filename)
        # Generate safe filename
        import uuid
        safe_name = f"{prefix}_{uuid.uuid4().hex}{ext}"
        return safe_name

    async def validate_image(self, file: UploadFile) -> tuple[bool, Optional[str]]:
        """
        Validate uploaded image file.
        
        Returns:
            (is_valid, error_message)
        """
        if not file.filename:
            return False, "No filename provided"

        if file.content_type not in self.ALLOWED_IMAGE_TYPES:
            return False, f"Image type not allowed. Allowed: {', '.join(self.ALLOWED_IMAGE_TYPES)}"

        if file.size and file.size > self.MAX_IMAGE_SIZE:
            return False, f"File size exceeds limit of {self.MAX_IMAGE_SIZE // 1024 // 1024} MB"

        # Read and validate image
        try:
            content = await file.read()
            img = Image.open(BytesIO(content))
            img.verify()
            
            # Reset file position for later read
            await file.seek(0)
            return True, None
        except Exception as e:
            _logger.warning("branding_service.image_validation_failed error=%s", str(e))
            return False, f"Invalid image: {str(e)}"

    async def upload_logo(self, org_id: str, file: UploadFile) -> tuple[bool, str, Optional[str]]:
        """
        Upload and optimize organization logo.
        
        Returns:
            (success, filename_or_error, relative_url)
        """
        # Validate
        is_valid, error = await self.validate_image(file)
        if not is_valid:
            return False, error, None

        try:
            # Read and optimize image
            content = await file.read()
            img = Image.open(BytesIO(content))
            
            # Resize to standard dimensions if needed
            if img.size != (self.DEFAULT_LOGO_WIDTH, self.DEFAULT_LOGO_HEIGHT):
                img.thumbnail((self.DEFAULT_LOGO_WIDTH, self.DEFAULT_LOGO_HEIGHT), Image.Resampling.LANCZOS)
            
            # Convert RGBA to RGB if necessary (for JPEG compatibility)
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg

            # Generate safe filename
            org_dir = self._get_org_upload_dir(org_id)
            safe_filename = self._sanitize_filename(file.filename, "logo")
            file_path = os.path.join(org_dir, safe_filename)

            # Save optimized image
            img.save(file_path, format="PNG", optimize=True, quality=90)
            
            # Generate relative URL for API responses
            relative_url = f"/uploads/{org_id}/branding/{safe_filename}"
            
            _logger.info(
                "branding_service.logo_uploaded org_id=%s filename=%s size=%d",
                org_id, safe_filename, os.path.getsize(file_path)
            )
            
            return True, safe_filename, relative_url
        except Exception as e:
            _logger.error("branding_service.logo_upload_failed org_id=%s error=%s", org_id, str(e))
            return False, f"Upload failed: {str(e)}", None

    async def upload_favicon(self, org_id: str, file: UploadFile) -> tuple[bool, str, Optional[str]]:
        """
        Upload and optimize favicon.
        
        Favicons should be square, small format.
        
        Returns:
            (success, filename_or_error, relative_url)
        """
        # Validate
        is_valid, error = await self.validate_image(file)
        if not is_valid:
            return False, error, None

        try:
            # Read and optimize image
            content = await file.read()
            img = Image.open(BytesIO(content))
            
            # Resize to 32x32 (standard favicon)
            img.thumbnail((32, 32), Image.Resampling.LANCZOS)
            
            # Pad to make square if necessary
            if img.size[0] != img.size[1]:
                size = max(img.size)
                new_img = Image.new("RGB", (size, size), (255, 255, 255))
                offset = ((size - img.size[0]) // 2, (size - img.size[1]) // 2)
                new_img.paste(img, offset)
                img = new_img

            # Generate safe filename
            org_dir = self._get_org_upload_dir(org_id)
            safe_filename = self._sanitize_filename(file.filename, "favicon")
            file_path = os.path.join(org_dir, safe_filename)

            # Save as ICO or PNG
            if safe_filename.endswith(".ico"):
                img.save(file_path, format="ICO")
            else:
                img.save(file_path, format="PNG", optimize=True)
            
            # Generate relative URL
            relative_url = f"/uploads/{org_id}/branding/{safe_filename}"
            
            _logger.info(
                "branding_service.favicon_uploaded org_id=%s filename=%s",
                org_id, safe_filename
            )
            
            return True, safe_filename, relative_url
        except Exception as e:
            _logger.error("branding_service.favicon_upload_failed org_id=%s error=%s", org_id, str(e))
            return False, f"Upload failed: {str(e)}", None

    def delete_asset(self, org_id: str, filename: str) -> bool:
        """Delete a branding asset."""
        try:
            org_dir = self._get_org_upload_dir(org_id)
            file_path = os.path.join(org_dir, filename)
            
            # Security: ensure we're deleting within org's directory
            real_path = os.path.realpath(file_path)
            real_org_dir = os.path.realpath(org_dir)
            
            if not real_path.startswith(real_org_dir):
                _logger.error("branding_service.delete_path_traversal_attempt org_id=%s filename=%s", org_id, filename)
                return False

            if os.path.exists(file_path):
                os.remove(file_path)
                _logger.info("branding_service.asset_deleted org_id=%s filename=%s", org_id, filename)
                return True
            return False
        except Exception as e:
            _logger.error("branding_service.delete_failed org_id=%s error=%s", org_id, str(e))
            return False


# Global branding service instance
_branding_service: Optional[BrandingService] = None


def initialize_branding_service(upload_dir: Optional[str] = None) -> BrandingService:
    """Initialize the global branding service."""
    global _branding_service
    _branding_service = BrandingService(upload_dir)
    return _branding_service


def get_branding_service() -> BrandingService:
    """Get the global branding service."""
    if _branding_service is None:
        raise RuntimeError("Branding service not initialized")
    return _branding_service
