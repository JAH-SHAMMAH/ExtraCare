from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import time
import logging

from app.config import get_settings
from app.core.logging import configure_logging
from app.database import init_db
from app.routers import auth, users, analytics, imports, me, organizations, admin, usage as usage_router, notifications, ai, payments, hr, hr_development, leave as leave_router, messenger as messenger_router, feed as feed_router, live as live_router, dashboard as dashboard_router, branding
from app.services.usage import start_flusher, stop_flusher, track, module_from_path
from app.routers.modules import school, hospital, business
from app.routers import support as support_router
from app.routers import remita as remita_router
from app.routers import fee_payments as fee_payments_router
from app.routers import hr_extended as hr_extended_router
from app.routers import search as search_router
from app.routers import upload as upload_router
from app.routers.modules import (
    classroom,
    cbt,
    behaviour,
    feedback as feedback_router,
    clubs,
    journals,
    tuckshop,
    library,
    sms as sms_router,
    transport as transport_router,
    attendance as attendance_router,
    parents as parents_router,
    admissions as admissions_router,
    academics as academics_router,
    pastoral as pastoral_router,
    medical as medical_router,
    finance as finance_router,
    finance_ops as finance_ops_router,
    wallet as wallet_router,
    operations as operations_router,
    facility as facility_router,
    biometric as biometric_router,
    platform as platform_router,
)

settings = get_settings()
configure_logging(level=settings.LOG_LEVEL, fmt=settings.resolved_log_format)
logger = logging.getLogger("extracare")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting %s...", settings.APP_NAME)
    await init_db()
    logger.info("Database initialized.")
    start_flusher()
    logger.info("Usage flusher started.")

    # Initialize payment resolver for multi-tenant payment orchestration
    from app.services.payment_resolver import initialize_payment_resolver
    initialize_payment_resolver(settings)
    logger.info("Payment resolver initialized.")

    # Initialize branding service for logo uploads
    from app.services.branding_service import initialize_branding_service
    initialize_branding_service(settings.UPLOAD_DIR if hasattr(settings, "UPLOAD_DIR") else None)
    logger.info("Branding service initialized.")

    # Wire the real billing provider when a Paystack secret is configured.
    # Unset ⇒ leave the Noop provider in place so dev keeps working, and
    # /payments/* returns a clear 503 instead of fake success.
    if settings.PAYSTACK_SECRET_KEY:
        from app.services.billing import set_billing_provider
        from app.services.paystack import PaystackProvider
        set_billing_provider(PaystackProvider(
            secret_key=settings.PAYSTACK_SECRET_KEY,
            public_key=settings.PAYSTACK_PUBLIC_KEY,
            api_url=settings.PAYSTACK_API_URL,
            callback_url=settings.PAYSTACK_CALLBACK_URL,
        ))
        logger.info("Paystack provider wired.")

    yield
    await stop_flusher()
    logger.info("Shutting down %s.", settings.APP_NAME)


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="Dedicated school portal for Fairview School — students, parents, teachers, HR, finance & academics.",
    version=settings.APP_VERSION,
    # Docs surface is useful in dev/staging but hidden in prod by default to
    # reduce surface area. Flip ENABLE_API_DOCS=true to expose it anywhere.
    docs_url="/api/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/api/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/api/openapi.json" if settings.ENABLE_API_DOCS else None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    # Also allow the dev frontend served from any private-LAN IP on :3000, so the
    # app can be opened on a phone over Wi-Fi without hardcoding the machine's IP.
    allow_origin_regex=r"http://(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}):3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)


import contextvars

# Per-request DB time accumulator. SQLAlchemy's before/after_cursor_execute
# events increment this; the middleware reads it and emits one structured
# log line per request so we can see total vs DB time without sprinkling
# timers through every handler.
_db_time_ms_ctx: contextvars.ContextVar[float] = contextvars.ContextVar(
    "db_time_ms", default=0.0
)

from sqlalchemy import event
from app.database import engine


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _db_time_before(conn, cursor, statement, params, context, executemany):
    context._query_start = time.perf_counter()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _db_time_after(conn, cursor, statement, params, context, executemany):
    start = getattr(context, "_query_start", None)
    if start is None:
        return
    dur_ms = (time.perf_counter() - start) * 1000
    try:
        _db_time_ms_ctx.set(_db_time_ms_ctx.get() + dur_ms)
    except LookupError:
        pass


@app.middleware("http")
async def csrf_protect_middleware(request: Request, call_next):
    """Double-submit CSRF guard for COOKIE-authenticated mutations only.

    Active only when cookie-auth is enabled. Bearer/API clients (Authorization
    header) are exempt — an attacker page cannot set that header, so they are
    not CSRF-vulnerable. The auth-bootstrap routes are exempt (no cookie yet /
    they mint it). For a cookie-authenticated mutating request we require the
    X-CSRF-Token header to equal the readable csrf_token cookie.
    """
    if settings.COOKIE_AUTH_ENABLED and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        path = request.url.path
        has_bearer = request.headers.get("Authorization", "").lower().startswith("bearer ")
        has_cookie = "access_token" in request.cookies
        exempt = any(path.endswith(p) for p in (
            "/auth/login", "/auth/register", "/auth/refresh", "/auth/logout",
        ))
        if has_cookie and not has_bearer and not exempt:
            sent = request.headers.get("X-CSRF-Token")
            expected = request.cookies.get("csrf_token")
            if not sent or not expected or sent != expected:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF token missing or invalid."},
                )
    return await call_next(request)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    token = _db_time_ms_ctx.set(0.0)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        db_ms = _db_time_ms_ctx.get()
        _db_time_ms_ctx.reset(token)

    response.headers["X-Response-Time"] = f"{elapsed:.1f}ms"
    response.headers["X-DB-Time"] = f"{db_ms:.1f}ms"

    # Payload size is only known when the handler set Content-Length (it
    # isn't always present — streaming / chunked responses skip it). For
    # the two diagnostic endpoints we care about, always log size so the
    # operator can flag unexpected bloat.
    content_length = response.headers.get("content-length")
    path = request.url.path
    if path.endswith("/analytics/overview") or path.endswith("/analytics/activity-feed"):
        size_bytes = int(content_length) if content_length else -1
        flag = " LARGE" if 0 < size_bytes > 50_000 else ""
        logger.info(
            "analytics_endpoint path=%s status=%s total_ms=%.1f db_ms=%.1f bytes=%d%s",
            path, response.status_code, elapsed, db_ms, size_bytes, flag,
        )

    # One structured log line per request. Slow paths (>100ms) are the
    # actionable ones — everything below that is background noise.
    if elapsed >= 100:
        logger.info(
            "slow_request path=%s method=%s status=%s total_ms=%.1f db_ms=%.1f",
            path, request.method, response.status_code, elapsed, db_ms,
        )

    # Download-bug audit: flag any response the browser would treat as a
    # download instead of rendering — either an explicit Content-Disposition
    # or a non-JSON/HTML content-type on an /api path. /uploads is the
    # legitimate media mount and is excluded. Anything that lights up here
    # without being whitelisted is almost certainly the mis-behaving route
    # the user keeps hitting.
    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
    content_disposition = response.headers.get("content-disposition")
    is_static = path.startswith("/uploads/") or path.startswith("/static/")
    is_docs = path.startswith("/api/docs") or path.startswith("/api/redoc") or path == "/api/openapi.json"
    if not is_static and not is_docs:
        expected = content_type in (
            "application/json",
            "text/html",
            "text/plain",
            "",  # 204 No Content etc.
        )
        if content_disposition or (path.startswith("/api/") and not expected):
            logger.warning(
                "download_audit path=%s method=%s status=%s content_type=%s disposition=%s",
                path, request.method, response.status_code,
                content_type or "-", content_disposition or "-",
            )

    # Usage tracking runs AFTER the response so org_id populated by auth
    # deps is available on request.state. Only successful module-scoped
    # calls count; 4xx/5xx don't inflate usage.
    if 200 <= response.status_code < 400:
        org_id = getattr(request.state, "org_id", None)
        module = module_from_path(request.url.path)
        if org_id and module:
            track(org_id, module, "request")
    return response


# ── Exception Handlers ────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Flatten Pydantic validation errors to a human-readable string.

    FastAPI's default response is `{"detail": [{loc, msg, type}, ...]}` —
    the frontend does `err.response.data.detail || fallback`, which with a
    truthy list ends up toasting `[object Object]`. Collapsing to a
    semicolon-joined `"field: message"` string keeps the same `{detail: str}`
    envelope every other endpoint uses, so the toast surfaces the real
    reason (e.g. "date_of_birth: input is not a valid date").
    """
    parts: list[str] = []
    for err in exc.errors():
        # `loc` is ("body", "field") for request-body errors; drop the
        # transport frame so the user sees just the field name.
        loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query", "path")]
        field = ".".join(loc) if loc else "input"
        msg = err.get("msg", "invalid")
        parts.append(f"{field}: {msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(parts) or "Invalid request."},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "traceback": tb},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error. The team has been notified."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

API_V1 = "/api/v1"

app.include_router(auth.router, prefix=API_V1)
app.include_router(users.router, prefix=API_V1)
app.include_router(analytics.router, prefix=API_V1)
app.include_router(analytics.org_router, prefix=API_V1)
app.include_router(school.router, prefix=API_V1)
# Hospital & Business verticals are deprecated for the Fairview School Portal.
# Their code is retained for stability/reversibility but is not mounted in
# single-school mode, so the API surface is school-only. Flip
# SINGLE_SCHOOL_MODE=false to restore the multi-industry platform.
if not settings.SINGLE_SCHOOL_MODE:
    app.include_router(hospital.router, prefix=API_V1)
    app.include_router(business.router, prefix=API_V1)
app.include_router(imports.router, prefix=API_V1)
app.include_router(me.router, prefix=API_V1)
app.include_router(organizations.router, prefix=API_V1)
# app.include_router(branding.router, prefix=API_V1)
app.include_router(admin.router, prefix=API_V1)
app.include_router(usage_router.router, prefix=API_V1)
app.include_router(notifications.router, prefix=API_V1)
app.include_router(ai.router, prefix=API_V1)
app.include_router(payments.router, prefix=API_V1)
app.include_router(hr.router, prefix=API_V1)
app.include_router(hr_development.router, prefix=API_V1)
app.include_router(leave_router.router, prefix=API_V1)
app.include_router(messenger_router.router, prefix=API_V1)
app.include_router(feed_router.router, prefix=API_V1)
app.include_router(live_router.router, prefix=API_V1)
app.include_router(search_router.router, prefix=API_V1)
app.include_router(upload_router.router, prefix=API_V1)

# Static file mount for uploaded media (/uploads/<org_id>/<file>). Path is
# configurable via UPLOAD_DIR. We ensure the dir exists so the mount doesn't
# 500 in fresh environments.
_upload_root = Path(settings.UPLOAD_DIR)
_upload_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_upload_root)), name="uploads")

# School Experience Layer — mounted under /api/v1 with their own prefixes
# (/classroom, /cbt, /behaviour, /feedback, /clubs, /journals, /tuckshop).
# Each router pins require_module("school") so they only answer when the
# tenant has the school module enabled.
app.include_router(classroom.router, prefix=API_V1)
app.include_router(cbt.router, prefix=API_V1)
app.include_router(behaviour.router, prefix=API_V1)
app.include_router(feedback_router.router, prefix=API_V1)
app.include_router(clubs.router, prefix=API_V1)
app.include_router(journals.router, prefix=API_V1)
app.include_router(tuckshop.router, prefix=API_V1)
app.include_router(library.router, prefix=API_V1)
app.include_router(sms_router.router, prefix=API_V1)
app.include_router(transport_router.router, prefix=API_V1)
app.include_router(attendance_router.router, prefix=API_V1)
app.include_router(parents_router.router, prefix=API_V1)
app.include_router(admissions_router.router, prefix=API_V1)
app.include_router(academics_router.router, prefix=API_V1)
app.include_router(pastoral_router.router, prefix=API_V1)
app.include_router(medical_router.router, prefix=API_V1)
app.include_router(finance_router.router, prefix=API_V1)
app.include_router(finance_ops_router.router, prefix=API_V1)
app.include_router(wallet_router.router, prefix=API_V1)
app.include_router(operations_router.router, prefix=API_V1)
app.include_router(facility_router.router, prefix=API_V1)
app.include_router(biometric_router.router, prefix=API_V1)
app.include_router(biometric_router.ingest_router, prefix=API_V1)   # device-token auth (no user session)
app.include_router(platform_router.router, prefix=API_V1)
app.include_router(dashboard_router.router, prefix=API_V1)
app.include_router(support_router.router, prefix=API_V1)
app.include_router(remita_router.router, prefix=API_V1)
app.include_router(fee_payments_router.router, prefix=API_V1)
app.include_router(hr_extended_router.router, prefix=API_V1)


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["System"])
async def root():
    return {"message": "ExtraCare ERP API", "docs": "/api/docs"}
