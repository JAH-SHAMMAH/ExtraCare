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
from app.services import crypto
from app.config import get_settings

_logger = logging.getLogger("extracare.payment_resolver")


class PaymentConfigError(RuntimeError):
    """A per-org payment secret exists but is unusable (e.g. it can't be decrypted
    because the encryption key is missing/rotated). Callers MUST fail loud (503)
    rather than fall back to the platform account — silently routing a school's fees
    to the platform's Paystack key is a tenant-isolation / financial bug."""


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
        # This resolver builds a PaystackProvider, so scope the lookup to the org's
        # active Paystack config. `.first()` (not scalar_one_or_none) is deliberate:
        # an org may now have configs for several providers, so a single-row assertion
        # would crash. provider_type lets a caller target a specific provider.
        query = (
            select(TenantPaymentSettings)
            .where(
                TenantPaymentSettings.org_id == org_id,
                TenantPaymentSettings.provider == (provider_type or PaymentProvider.PAYSTACK),
                TenantPaymentSettings.is_active == True,
                TenantPaymentSettings.is_deleted == False,
            )
            .order_by(TenantPaymentSettings.created_at.desc())
        )
        settings = (await db.execute(query)).scalars().first()

        # A real per-org config carries an encrypted secret. Decrypt it here (this is
        # the ONE point of use) and build a provider bound to THIS school's account —
        # so fee payments settle to them, not the platform env key.
        if settings and settings.encrypted_secret_key:
            _logger.info("payment_resolver.tenant_config_found org_id=%s provider=%s", org_id, settings.provider)
            try:
                secret_key = crypto.decrypt(settings.encrypted_secret_key)
            except Exception as exc:
                # A stored-but-undecryptable secret means a key/config problem. Do NOT
                # silently fall back to the platform account (that would route a
                # school's fees to the wrong place) — raise a dedicated error the
                # caller turns into a hard 503. Fail loud, never fail open.
                _logger.error("payment_resolver.decrypt_failed org_id=%s err=%s", org_id, exc)
                raise PaymentConfigError(
                    f"Payment secret for organization {org_id} could not be decrypted "
                    "(encryption key missing or rotated). Fix the key or re-enter the gateway secret."
                ) from exc
            metadata = settings.metadata_ or {}
            public_key = metadata.get("public_key") or self.settings.PAYSTACK_PUBLIC_KEY
            return PaystackProvider(
                secret_key=secret_key,
                public_key=public_key,
                api_url=self.settings.PAYSTACK_API_URL,
                callback_url=self.settings.PAYSTACK_CALLBACK_URL,
            )

        # No per-org secret configured (or only a platform-fallback placeholder row)
        # → use the platform provider (env key), preserving today's behaviour.
        _logger.warning("payment_resolver.using_platform_provider org_id=%s", org_id)
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
