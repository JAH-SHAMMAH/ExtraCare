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
from app.services.flutterwave import FlutterwaveProvider
from app.services import crypto
from app.config import get_settings

_logger = logging.getLogger("extracare.payment_resolver")


class PaymentConfigError(RuntimeError):
    """A per-org payment secret exists but is unusable (e.g. it can't be decrypted
    because the encryption key is missing/rotated, OR it's for a provider we don't
    have an adapter for yet). Callers MUST fail loud (503) rather than fall back to
    the platform account — silently routing a school's fees to the platform's
    Paystack key is a tenant-isolation / financial bug."""


# Providers we can actually BUILD a working adapter for TODAY. A per-org config for a
# provider NOT in this set is treated as "configured but unsupported": the fee flow
# fails loud rather than silently settling to the platform account / wrong gateway.
# (Remita has its OWN flow/router + resolver, so it's not built through this factory.)
SUPPORTED_PROVIDERS = {PaymentProvider.PAYSTACK, PaymentProvider.FLUTTERWAVE}


def build_provider(provider: PaymentProvider, *, secret_key: str, public_key: str | None, settings):
    """Factory: construct the payment adapter for ``provider`` from ALREADY-DECRYPTED
    credentials. This is the single extension point for new providers — add a branch
    here and register the enum in ``SUPPORTED_PROVIDERS``. Raises ``PaymentConfigError``
    for a provider with no adapter yet."""
    if provider == PaymentProvider.PAYSTACK:
        return PaystackProvider(
            secret_key=secret_key,
            public_key=public_key or settings.PAYSTACK_PUBLIC_KEY,
            api_url=settings.PAYSTACK_API_URL,
            callback_url=settings.PAYSTACK_CALLBACK_URL,
        )
    if provider == PaymentProvider.FLUTTERWAVE:
        return FlutterwaveProvider(
            secret_key=secret_key,
            base_url=settings.FLUTTERWAVE_BASE_URL,
            callback_url=settings.FLUTTERWAVE_CALLBACK_URL,
        )
    raise PaymentConfigError(
        f"Payment provider '{provider.value}' is configured for this school but is not yet "
        "supported for live payments. Configure Paystack, or contact support."
    )


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
        # The org's active per-org configs that carry a usable (encrypted) secret.
        # `.all()` (not scalar_one_or_none) because an org may configure several
        # providers; provider_type lets a caller target one.
        query = (
            select(TenantPaymentSettings)
            .where(
                TenantPaymentSettings.org_id == org_id,
                TenantPaymentSettings.is_active == True,
                TenantPaymentSettings.is_deleted == False,
                TenantPaymentSettings.encrypted_secret_key.isnot(None),
            )
            .order_by(TenantPaymentSettings.created_at.desc())
        )
        if provider_type:
            query = query.where(TenantPaymentSettings.provider == provider_type)
        rows = (await db.execute(query)).scalars().all()

        # Prefer a config whose provider we can actually build. Decrypt at the point
        # of use and build via the factory — the provider is bound to THIS school's
        # account, so fee payments settle to them, not the platform env key.
        supported = [r for r in rows if r.provider in SUPPORTED_PROVIDERS]
        if supported:
            row = supported[0]
            _logger.info("payment_resolver.tenant_config_found org_id=%s provider=%s", org_id, row.provider)
            try:
                secret_key = crypto.decrypt(row.encrypted_secret_key)
            except Exception as exc:
                # Stored-but-undecryptable secret → key/config problem. Do NOT fall
                # back to the platform account (wrong-place settlement). Fail loud.
                _logger.error("payment_resolver.decrypt_failed org_id=%s err=%s", org_id, exc)
                raise PaymentConfigError(
                    f"Payment secret for organization {org_id} could not be decrypted "
                    "(encryption key missing or rotated). Fix the key or re-enter the gateway secret."
                ) from exc
            md = row.metadata_ or {}
            return build_provider(row.provider, secret_key=secret_key, public_key=md.get("public_key"), settings=self.settings)

        # The org configured ONLY an unsupported provider (e.g. Flutterwave — no
        # adapter yet). Fail loud: silently using the platform Paystack account would
        # settle their fees to the wrong gateway with no visible error.
        if rows:
            _logger.error("payment_resolver.unsupported_provider org_id=%s provider=%s", org_id, rows[0].provider)
            raise PaymentConfigError(
                f"Payment provider '{rows[0].provider.value}' is configured for this school but is not yet "
                "supported for live payments. Configure Paystack, or contact support."
            )

        # No per-org config → platform provider (env key), preserving today's behaviour.
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
