"""
AI assistant — single entry point, module-aware.

POST /api/v1/ai/assist with {module, task, context}. Enforcement layers:
  1. Feature flag `ai_assistant` must be on for the tenant.
  2. The target `module` must be in the tenant's `modules_enabled`.
  3. The tenant's plan must actually permit the module (plan + cap).
  4. The caller must hold `<module>:read`.
  5. Onboarding soft-gate applies — pre-done tenants only get their
     primary vertical.

We deliberately replicate the module/plan/perm checks from
`require_role_module` here instead of wrapping the dep, because the
module name arrives in the request body (not the path), so a static
`Depends(require_role_module("school"))` isn't an option.

Safety rules the handler code enforces:
  • No DB access inside assistant handlers — they see `context` only.
  • No hallucinated IDs — output is a deterministic template over
    whatever the caller passed in.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.features import require_feature
from app.core.plans import (
    module_allowed_by_plan,
    modules_within_cap,
    plan_for,
    plan_limit_detail,
)
from app.core.tenant import bump_denial
from app.core.workspace import effective_modules_for_org, is_module_enabled_for_org
from app.database import get_db
from app.deps import get_current_active_user
from app.models.organization import Organization
from app.models.user import User
from app.services import ai as ai_svc
from app.services import notifications as notif_svc
from app.services.onboarding import module_is_in_primary_scope
from app.services.usage import track as track_usage


_logger = logging.getLogger("extracare.ai")


router = APIRouter(prefix="/ai", tags=["AI Assistant"])


AIModuleLiteral = Literal["school", "hospital", "business"]


class AIAssistRequest(BaseModel):
    module: AIModuleLiteral
    task: str = Field(..., min_length=1, max_length=64)
    # Free-form dict — handlers know which keys they care about. Cap the
    # payload size defensively; assistants only need light context.
    context: dict[str, Any] | None = None


class AIAssistMeta(BaseModel):
    module: str
    task: str
    # Tokens aren't tracked by the current Noop provider. Keep the field
    # in the wire shape so a future adapter can fill it without a schema
    # migration on the client.
    tokens_used: int | None = None
    provider: str


class AIAssistResponse(BaseModel):
    result: str
    meta: AIAssistMeta


async def _resolve_org(
    request: Request, db: AsyncSession, current_user: User
) -> Organization:
    org: Organization | None = getattr(request.state, "org", None)
    if org is None:
        org = (await db.execute(
            select(Organization).where(
                Organization.id == current_user.org_id,
                Organization.is_active == True,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=400, detail="Tenant not resolved.")
        request.state.org = org
        request.state.org_id = org.id
    return org


def _enforce_module_access(
    request: Request, org: Organization, current_user: User, module: str
) -> None:
    """Module + plan + onboarding + permission checks. Mirrors the
    sequence in `require_role_module` so /ai/assist stays consistent
    with the rest of the gated surface."""
    # (1) Module enabled on the org
    if not is_module_enabled_for_org(org, module):
        bump_denial("module_access_denied", org.id, module)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Module '{module}' is not enabled for your organization.",
        )

    # (2) Onboarding soft-gate — same rule as module routes
    if org.onboarding_completed_at is None and not current_user.is_superadmin:
        if not module_is_in_primary_scope(org, module):
            bump_denial("onboarding_incomplete", org.id, module)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "onboarding_incomplete",
                    "onboarding_step": org.onboarding_step or "modules",
                },
            )

    # (3) Plan allows the module + within module cap
    plan = plan_for(org.subscription_tier)
    if not module_allowed_by_plan(plan, module) or not modules_within_cap(
        plan, effective_modules_for_org(org)
    ):
        bump_denial("plan_module_denied", org.id, module)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=plan_limit_detail(
                reason="module_not_allowed",
                current_plan=plan.tier,
            ),
        )

    # (4) Permission — canonical `<module>:read`
    required_perm = f"{module}:read"
    if not current_user.has_permission(required_perm):
        bump_denial("role_permission_denied", org.id, required_perm)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied. Required: '{required_perm}'",
        )


async def _maybe_first_use_notification(
    db: AsyncSession, org: Organization, user: User
) -> None:
    """Fire a one-shot `system` notification the first time any user in
    the tenant successfully calls the assistant. Detection is a cheap
    existence check against the notifications table. Swallows errors so
    the caller's response isn't affected."""
    try:
        from sqlalchemy import func
        from app.models.notification import Notification, TYPE_SYSTEM

        seen = (await db.execute(
            select(func.count(Notification.id)).where(
                Notification.org_id == org.id,
                Notification.type == TYPE_SYSTEM,
                Notification.title == "AI assistant is now active",
            )
        )).scalar() or 0
        if seen:
            return
        await notif_svc.notify(
            org_id=org.id,
            user_id=None,
            type=TYPE_SYSTEM,
            title="AI assistant is now active",
            message="Your organization just used the AI assistant for the first time.",
            payload={"first_user_id": user.id},
            session=db,
        )
    except Exception:
        # Notifications must never break the assistant response.
        pass


@router.post(
    "/assist",
    response_model=AIAssistResponse,
    summary="Run a module-aware AI assistant task",
    dependencies=[Depends(require_feature("ai_assistant"))],
)
async def assist(
    body: AIAssistRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org = await _resolve_org(request, db, current_user)
    _enforce_module_access(request, org, current_user, body.module)

    # ai.request fires for every enforced, valid invocation — even if
    # dispatch rejects the task. This matches how module `request`
    # counts work (the request happened, whether the handler liked it
    # or not).
    track_usage(org.id, body.module, "ai.request")

    try:
        result = ai_svc.dispatch(body.module, body.task, body.context)
    except KeyError:
        # Unknown module — should be prevented by the Literal schema,
        # but keep a defensive branch for safety.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported module: {body.module!r}.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unsupported_task",
                "message": str(exc),
                "supported_tasks": list(ai_svc.supported_tasks(body.module)),
            },
        )
    except Exception as exc:
        _logger.exception("ai dispatch failed: %s", exc)
        raise HTTPException(status_code=500, detail="AI assistant failed.")

    track_usage(org.id, body.module, "ai.success")
    await _maybe_first_use_notification(db, org, current_user)
    await db.commit()

    from app.services.ai.provider import get_ai_provider
    provider = get_ai_provider()

    return AIAssistResponse(
        result=result,
        meta=AIAssistMeta(
            module=body.module,
            task=body.task,
            tokens_used=None,
            provider=provider.name,
        ),
    )
