from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Fairview School Portal"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True

    # ── Single-School (Fairview) mode ────────────────────────────────────────
    # This deployment is a dedicated portal for ONE school, not a multi-tenant
    # SaaS. The underlying tenant machinery (org_id scoping, the workspace
    # engine) is left intact for stability and reversibility — single-school
    # behaviour is enforced at the boundary (auth, router mounting, UI) via
    # these flags rather than by deleting the multi-industry core.
    #
    # When True:
    #   • Login resolves the one canonical org server-side (org_slug ignored).
    #   • Only emails on ALLOWED_EMAIL_DOMAIN may authenticate.
    #   • Public organisation registration is disabled.
    #   • Hospital/Business verticals are not mounted or surfaced.
    SINGLE_SCHOOL_MODE: bool = True
    # The only org users authenticate against in single-school mode. Must match
    # the seeded organisation's slug (see scripts/seed_fairview_school.py).
    SCHOOL_ORG_SLUG: str = "fairview-school"
    SCHOOL_NAME: str = "Fairview School"
    # Email-domain allow-list for authentication. Domain validation is
    # necessary-but-not-sufficient: the user must ALSO be a registered, active
    # account (no auto-provisioning). Stored without the leading "@"; compared
    # case-insensitively — see allowed_email_domain below.
    ALLOWED_EMAIL_DOMAIN: str = "fairviewschoolng.com"

    # ── Attendance ───────────────────────────────────────────────────────────
    # Cutoffs (school-local "HH:MM") used to derive a daily attendance status
    # from timestamped check-in/check-out events. A check-in after
    # SCHOOL_LATE_AFTER is marked LATE; a check-out before
    # SCHOOL_EARLY_DEPARTURE_BEFORE flags an early departure. Times are
    # interpreted in the organisation's timezone (org.timezone).
    SCHOOL_LATE_AFTER: str = "08:00"
    SCHOOL_EARLY_DEPARTURE_BEFORE: str = "14:00"

    # ── Security ─────────────────────────────────────────────────────────────
    # Must be overridden in staging/production — see model_validator below.
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ─────────────────────────────────────────────────────────────
    # Driver-agnostic: the app runs on any async SQLAlchemy dialect. Examples:
    #   sqlite+aiosqlite:///./extracare.db             (dev)
    #   mysql+aiomysql://user:pw@host:3306/extracare   (TiDB / MySQL)
    #   sqlite+libsql://<db>.turso.io?authToken=...    (Turso / libSQL)
    #   postgresql+asyncpg://user:pw@host:5432/db      (Postgres)
    DATABASE_URL: str = "sqlite+aiosqlite:///./extracare.db"
    DATABASE_ECHO: bool = False

    # Prod DBs need pool tuning; SQLite ignores these. Values are conservative
    # defaults tuned for a single gunicorn worker — multiply by worker count
    # to reason about total connections at the DB.
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 1800  # recycle before most cloud idle-kills.

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # ── Email ────────────────────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@fairviewschoolng.com"

    # ── File Storage ─────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # ── Subscription Tiers ───────────────────────────────────────────────────
    FREE_TIER_USER_LIMIT: int = 10
    STARTER_TIER_USER_LIMIT: int = 50
    GROWTH_TIER_USER_LIMIT: int = 500

    # ── WebRTC / TURN ────────────────────────────────────────────────────────
    # STUN is enough inside permissive networks; schools on symmetric NAT or
    # restrictive firewalls need a TURN relay. Two credential modes:
    #   1) Ephemeral (recommended): set TURN_SECRET — we mint time-limited
    #      HMAC-SHA1 credentials (coturn "use-auth-secret") per client.
    #   2) Static: set TURN_USERNAME + TURN_CREDENTIAL — easy to set up,
    #      weaker security since the same creds ship to every browser.
    # Leave everything blank to stay STUN-only.
    # Comma-separated URLs (str, not list) so env parsing stays hassle-free on
    # platforms that only expose plain string env vars. Parsed at usage time.
    TURN_URLS: str = ""  # e.g. "turn:turn.example.com:3478,turns:turn.example.com:5349"
    TURN_USERNAME: str = ""
    TURN_CREDENTIAL: str = ""
    TURN_SECRET: str = ""
    TURN_TTL_SECONDS: int = 3600  # how long minted creds stay valid
    STUN_URLS: str = "stun:stun.l.google.com:19302"

    # ── Paystack ─────────────────────────────────────────────────────────────
    # Secret key — server-side only, never exposed to the frontend. Empty
    # string means "not configured" and the payments router falls back to
    # the Noop billing provider (dev default). In production the
    # model_validator below forces a real key.
    PAYSTACK_SECRET_KEY: str = ""
    # Public key — safe to ship to the client. Used if we ever swap to the
    # Popup.js inline flow; today we redirect to the hosted checkout.
    PAYSTACK_PUBLIC_KEY: str = ""
    # Base URL for the REST API — overridable so staging can point at a
    # mock and tests can stub the adapter without monkeypatching httpx.
    PAYSTACK_API_URL: str = "https://api.paystack.co"
    # Where Paystack redirects the user after checkout. The frontend reads
    # the `reference` query param and calls our verify endpoint.
    PAYSTACK_CALLBACK_URL: str = "http://localhost:3000/billing/callback"

    # ── Observability ────────────────────────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # pretty = human-readable (dev); json = one object per line (prod/shippers).
    # Blank lets the env default kick in based on ENVIRONMENT.
    LOG_FORMAT: Literal["pretty", "json", "auto"] = "auto"

    # ── Runtime behaviour ────────────────────────────────────────────────────
    # When true, the app runs Base.metadata.create_all on startup. Dev-only;
    # prod deployments must run Alembic migrations instead so the schema is
    # tracked and reviewable.
    AUTO_CREATE_SCHEMA: bool = True
    # Expose /api/docs and /api/redoc. Usually off in prod.
    ENABLE_API_DOCS: bool = True

    # ── Feature Flags ────────────────────────────────────────────────────────
    # Workspace isolation (gradual rollout):
    #   - false (default on deploy): Existing orgs use legacy code; new orgs use workspace system
    #   - true (after 2 weeks): All orgs use workspace system
    # Can be overridden per-org in the Organization model if needed.
    WORKSPACE_ISOLATION_ENABLED: bool = False

    # ── Validators ───────────────────────────────────────────────────────────
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        # Allow a comma-separated env string so platforms that don't support
        # JSON-list env vars (Render, Railway) can still configure CORS.
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def turn_url_list(self) -> list[str]:
        return [u.strip() for u in self.TURN_URLS.split(",") if u.strip()]

    @property
    def stun_url_list(self) -> list[str]:
        return [u.strip() for u in self.STUN_URLS.split(",") if u.strip()]

    @model_validator(mode="after")
    def _enforce_prod_safety(self):
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY.startswith("CHANGE_THIS"):
                raise ValueError(
                    "SECRET_KEY must be set to a secure value in production. "
                    "Generate one with: openssl rand -hex 32"
                )
            if self.DEBUG:
                # Debug mode leaks tracebacks into responses — never in prod.
                raise ValueError("DEBUG must be False in production.")
            if self.DATABASE_URL.startswith("sqlite"):
                # SQLite is unsafe for multi-worker prod deployments; flag it
                # loudly so deploys don't silently ship on it.
                raise ValueError(
                    "SQLite is not supported in production. Set DATABASE_URL "
                    "to MySQL/TiDB/Turso/PostgreSQL (async driver)."
                )
            if self.AUTO_CREATE_SCHEMA:
                raise ValueError(
                    "AUTO_CREATE_SCHEMA must be False in production — use "
                    "`alembic upgrade head` in your deploy step instead."
                )
            if not self.PAYSTACK_SECRET_KEY:
                # Payments won't work without this; fail fast at boot so we
                # never accept billing traffic against the Noop provider.
                raise ValueError(
                    "PAYSTACK_SECRET_KEY must be set in production."
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def allowed_email_domain(self) -> str:
        """Normalized auth domain: lower-cased, no leading '@'. Empty string
        disables the domain gate (any domain may authenticate)."""
        return self.ALLOWED_EMAIL_DOMAIN.strip().lstrip("@").lower()

    def email_allowed(self, email: str | None) -> bool:
        """True when single-school mode is off, no domain is configured, or
        the email ends with the allowed domain. Case-insensitive."""
        if not self.SINGLE_SCHOOL_MODE:
            return True
        domain = self.allowed_email_domain
        if not domain:
            return True
        return bool(email) and email.strip().lower().endswith("@" + domain)

    @property
    def resolved_log_format(self) -> Literal["pretty", "json"]:
        if self.LOG_FORMAT == "auto":
            return "json" if self.ENVIRONMENT in ("staging", "production") else "pretty"
        return self.LOG_FORMAT


@lru_cache
def get_settings() -> Settings:
    return Settings()
