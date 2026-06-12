"""
Payment Provider Resolver Service
==================================

Multi-tenant, multi-provider payment orchestration.

Each tenant can configure their own payment provider credentials.
This service dynamically resolves and validates the correct provider
for a given organization, ensuring no credential leakage across tenants.

Architecture:
- Providers are initialized with encrypted credentials at startup
- Provider selection is org-scoped (no cross-tenant access)
- Fallback chain: tenant-specific → platform-default (MVP) → error
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.organization import Organization
from app.models.payment import TenantPaymentSettings, PaymentProvider
from app.services.paystack import PaystackProvider
from app.config import get_settings

_logger = logging.getLogger("extracare.payment_resolver")


class PaymentProviderResolver:
    """
    Resolves the active payment provider for a given organization.
    
    NEVER exposes credentials to callers — only returns initialized provider.
    Provider handles all credential management internally.
    """

    def __init__(self, settings):
        """Initialize resolver with platform-level settings."""
        self.settings = settings
        # Platform-level Paystack provider (MVP fallback)
        self._platform_paystack: Optional[PaystackProvider] = None
        
    @property
    def platform_paystack(self) -> PaystackProvider:
        """
        Get or initialize platform-level Paystack provider.
        
        This is used as a fallback during MVP phase.
        In production, each tenant has their own provider configuration.
        """
        if not self._platform_paystack and self.settings.PAYSTACK_SECRET_KEY:
            self._platform_paystack = PaystackProvider(
                secret_key=self.settings.PAYSTACK_SECRET_KEY,
                public_key=self.settings.PAYSTACK_PUBLIC_KEY,
                callback_url=self.settings.PAYSTACK_CALLBACK_URL,
            )
        return self._platform_paystack

    async def resolve_for_org(
        self,
        org_id: str,
        db: AsyncSession,
        provider_type: Optional[PaymentProvider] = None,
    ) -> PaystackProvider:
        """
        Resolve the payment provider for a specific organization.
        
        Args:
            org_id: The organization ID
            db: Database session
            provider_type: Optional filter to specific provider type
            
        Returns:
            Initialized provider ready for use
            
        Raises:
            ValueError: If provider not configured for org
        """
        # Query tenant-specific payment settings
        query = select(TenantPaymentSettings).where(
            TenantPaymentSettings.org_id == org_id,
            TenantPaymentSettings.is_active == True,
            TenantPaymentSettings.is_deleted == False,
        )
        
        if provider_type:
            query = query.where(TenantPaymentSettings.provider == provider_type)
        
        result = await db.execute(query)
        settings = result.scalar_one_or_none()
        
        if settings:
            _logger.info(
                "payment_resolver.tenant_config_found org_id=%s provider=%s",
                org_id, settings.provider
            )
            # TODO: Decrypt credentials from encrypted storage
            # For now, this is a stub. In production:
            # secret_key = decrypt(settings.encrypted_secret_key)
            # public_key = decrypt(settings.encrypted_public_key)
            raise NotImplementedError(
                "Tenant-specific payment configuration requires decryption service"
            )
        
        # Fallback to platform provider during MVP
        _logger.warning(
            "payment_resolver.using_platform_provider org_id=%s",
            org_id
        )
        
        provider = self.platform_paystack
        if not provider:
            raise ValueError(
                f"No payment provider configured for organization {org_id}"
            )
        
        return provider

    async def get_active_provider_for_org(
        self,
        org: Organization,
        db: AsyncSession,
    ) -> Optional[PaymentProvider]:
        """
        Get the active payment provider type for an organization.
        
        Args:
            org: The organization
            db: Database session
            
        Returns:
            PaymentProvider enum or None if not configured
        """
        result = await db.execute(
            select(TenantPaymentSettings).where(
                TenantPaymentSettings.org_id == org.id,
                TenantPaymentSettings.is_active == True,
                TenantPaymentSettings.is_deleted == False,
            )
        )
        settings = result.scalar_one_or_none()
        return settings.provider if settings else None

    async def verify_provider_for_org(
        self,
        org_id: str,
        db: AsyncSession,
    ) -> bool:
        """
        Check if a verified payment provider is configured for an organization.
        
        Args:
            org_id: The organization ID
            db: Database session
            
        Returns:
            True if a verified provider is configured
        """
        result = await db.execute(
            select(TenantPaymentSettings).where(
                TenantPaymentSettings.org_id == org_id,
                TenantPaymentSettings.is_active == True,
                TenantPaymentSettings.is_verified == True,
                TenantPaymentSettings.is_deleted == False,
            )
        )
        return result.scalar_one_or_none() is not None


# Global resolver instance
_resolver: Optional[PaymentProviderResolver] = None


def initialize_payment_resolver(settings) -> PaymentProviderResolver:
    """Initialize the global payment provider resolver."""
    global _resolver
    _resolver = PaymentProviderResolver(settings)
    _logger.info("payment_resolver.initialized")
    return _resolver


def get_payment_resolver() -> PaymentProviderResolver:
    """Get the global payment provider resolver. Lazily initialize if needed."""
    global _resolver
    if _resolver is None:
        try:
            from app.config import get_settings
            settings = get_settings()
            _resolver = initialize_payment_resolver(settings)
        except Exception:
            raise RuntimeError("Payment resolver not initialized. Call initialize_payment_resolver first.")
    return _resolver
