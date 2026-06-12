"""
Onboarding flow — guided setup for fresh tenants.

Progression is strictly linear:
    modules → users → first_action → done

Each step's "completion condition" is checked against real DB state, not a
self-reported flag. That means a tenant that already has members + a student
will jump straight to `done` on their first /me call, and a tenant that
fakes a PATCH to skip ahead will be rejected. The frontend uses
`onboarding_step` to decide which guided screen to render.

Why derived-from-DB rather than a bitfield:
  • Imports and SQL seeds naturally advance state without us adding hooks.
  • If an admin deletes the last user, we don't need to "undo" progress —
    the condition stops being met on the next evaluation.

Enforcement lives in core/tenant.py — module routes 403 until `done`, which
forces fresh tenants through the flow rather than letting them skip it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.organization import Organization, IndustryType
from app.models.user import User

settings = get_settings()


# The canonical step order. Each step unlocks only after the prior one's
# condition is satisfied — no skipping, no going backwards.
STEPS = ("modules", "users", "first_action", "done")


def _step_index(step: str) -> int:
    try:
        return STEPS.index(step)
    except ValueError:
        return 0  # unknown → treat as fresh


# Industry → primary record model. These are the "you actually started
# using the product" signals. Any of them existing flips first_action.
#
# School is the first-class vertical. Hospital/Business are deprecated and
# imported lazily inside try/except so this module stays import-safe even if
# those vertical models are later removed (controlled deprecation).
def _primary_model_for(industry: IndustryType):
    from app.models.modules.school import Student

    if industry == IndustryType.SCHOOL:
        return [Student]

    models = [Student] if industry == IndustryType.HYBRID else []
    if industry in (IndustryType.HOSPITAL, IndustryType.HYBRID):
        try:
            from app.models.modules.hospital import Patient
            models.append(Patient)
        except Exception:
            pass
    if industry in (IndustryType.BUSINESS, IndustryType.HYBRID):
        try:
            from app.models.modules.business import Employee
            models.append(Employee)
        except Exception:
            pass
    return models


async def _has_primary_record(db: AsyncSession, org: Organization) -> bool:
    for model in _primary_model_for(org.industry):
        row = await db.execute(
            select(func.count(model.id)).where(model.org_id == org.id)
        )
        if (row.scalar() or 0) > 0:
            return True
    return False


async def _active_user_count(db: AsyncSession, org_id: str) -> int:
    row = await db.execute(
        select(func.count(User.id)).where(
            User.org_id == org_id, User.is_deleted == False  # noqa: E712
        )
    )
    return int(row.scalar() or 0)


async def evaluate(db: AsyncSession, org: Organization, *, commit: bool = True) -> str:
    """Recompute the furthest step the tenant has actually completed, write
    it back to the org row if it advanced, and return the new step.

    Passing commit=False lets callers batch this inside a larger transaction
    (e.g. the /auth/me flow, where we don't want to commit on every read)."""
    # Single-school portal: there is one pre-provisioned organisation and no
    # self-service multi-tenant onboarding wizard. Always "done" so the
    # onboarding gate in core/tenant.py is a no-op and module routes stay open.
    if settings.SINGLE_SCHOOL_MODE:
        return "done"

    if org.onboarding_completed_at is not None:
        return "done"

    # Start from whatever was persisted and try to advance.
    step = org.onboarding_step or "modules"

    if step == "modules" and (org.modules_enabled or []):
        step = "users"

    if step == "users" and await _active_user_count(db, org.id) >= 2:
        step = "first_action"

    if step == "first_action" and await _has_primary_record(db, org):
        step = "done"

    prior = org.onboarding_step or "modules"
    if step != prior:
        org.onboarding_step = step
        if step == "done" and org.onboarding_completed_at is None:
            org.onboarding_completed_at = datetime.now(timezone.utc)
            _track_lifecycle(org.id, "onboarding_completed")
        await _notify_step_advanced(db, org, prior, step)
        if commit:
            await db.commit()
            await db.refresh(org)

    return step


async def _notify_step_advanced(db: AsyncSession, org: Organization, prior: str, step: str) -> None:
    """Org-wide notification so admins see setup progress without polling
    /me. Fires on every advance including the final flip to 'done'."""
    try:
        from app.services import notifications as _notif
        from app.models.notification import TYPE_ONBOARDING_STEP
        if step == "done":
            title = "Onboarding complete"
            message = "Your organization is fully set up."
        else:
            title = f"Onboarding: {step.replace('_', ' ')}"
            message = _STEP_REQUIREMENTS.get(step, "")
        await _notif.notify(
            org_id=org.id,
            user_id=None,
            type=TYPE_ONBOARDING_STEP,
            title=title,
            message=message,
            payload={"previous_step": prior, "current_step": step},
            session=db,
        )
    except Exception:
        # Notifications must never break the onboarding write path.
        pass


def _track_lifecycle(org_id: str, event: str) -> None:
    """Drop a platform-scoped usage marker. Swallow the import to keep the
    evaluate() path safe even if the usage service is mid-rewrite."""
    try:
        from app.services.usage import track
        track(org_id, "platform", event)
    except Exception:
        pass


# ── Diagnostics ─────────────────────────────────────────────────────────────

# Human-readable "why this step is blocked" strings. Frontends + /debug
# views render these verbatim — keep them short and actionable.
_STEP_REQUIREMENTS: dict[str, str] = {
    "modules": "Choose at least one module to enable for your organization.",
    "users": "Invite at least one additional user so the team can collaborate.",
    "first_action": "Create your first primary record (student, patient, or employee) to go live.",
    "done": "Onboarding complete.",
}


async def diagnose(db: AsyncSession, org: Organization) -> dict:
    """Snapshot of current step, completion status, and the concrete
    requirement still outstanding. Used by the admin visibility endpoint
    and by the frontend's setup wizard to show 'what's next'."""
    step = await evaluate(db, org, commit=True)
    user_count = await _active_user_count(db, org.id)
    has_primary = await _has_primary_record(db, org)
    return {
        "org_id": org.id,
        "onboarding_step": step,
        "onboarding_completed": org.onboarding_completed_at is not None,
        "onboarding_completed_at": (
            org.onboarding_completed_at.isoformat()
            if org.onboarding_completed_at else None
        ),
        "requirement": _STEP_REQUIREMENTS.get(step, ""),
        "checks": {
            "modules_enabled_count": len(org.modules_enabled or []),
            "active_user_count": user_count,
            "has_primary_record": has_primary,
        },
    }


def primary_module_for(org: Organization) -> str | None:
    """The single module a tenant may use during onboarding — everything
    else stays gated. Rule: whichever module matches the org's industry,
    falling back to the first entry of modules_enabled for hybrid tenants."""
    from app.models.organization import IndustryType

    industry_map = {
        IndustryType.SCHOOL: "school",
        IndustryType.HOSPITAL: "hospital",
        IndustryType.BUSINESS: "business",
    }
    primary = industry_map.get(org.industry)
    if primary and primary in (org.modules_enabled or []):
        return primary
    mods = list(org.modules_enabled or [])
    return mods[0] if mods else None


# Sub-routes of the primary vertical that should stay open during onboarding
# alongside the module itself. Keeps the mapping consistent with the
# usage-tracking path map — school has many child routers.
_PRIMARY_COVERED_MODULES: dict[str, set[str]] = {
    "school": {"school", "behaviour", "cbt", "classroom", "clubs",
               "feedback", "journals", "tuckshop"},
    "hospital": {"hospital"},
    "business": {"business"},
}


def module_is_in_primary_scope(org: Organization, module_name: str) -> bool:
    """Is `module_name` part of the tenant's active (primary) module group?
    Used by require_role_module to soft-gate during onboarding — the
    active module stays reachable so users can explore while they finish
    setup; unrelated modules stay locked."""
    primary = primary_module_for(org)
    if primary is None:
        return False
    return module_name in _PRIMARY_COVERED_MODULES.get(primary, {primary})


def is_completed(org: Organization) -> bool:
    """Cheap, no-DB check for middleware hot paths."""
    return org.onboarding_completed_at is not None


async def advance(db: AsyncSession, org: Organization, target_step: str) -> str:
    """Manual advance via the PATCH endpoint. Refuses to skip ahead: the
    target must be the step *immediately* following the current one, AND
    the underlying condition must already be met (we re-evaluate first)."""
    if target_step not in STEPS:
        raise ValueError(f"Unknown onboarding step: {target_step}")

    # Re-evaluate from DB state first — lets a caller confirm auto-advance
    # too, not just force-push a step.
    current = await evaluate(db, org, commit=False)

    cur_i = _step_index(current)
    tgt_i = _step_index(target_step)
    if tgt_i < cur_i:
        # Idempotent: asking to "go back" just reports current state.
        return current
    if tgt_i > cur_i:
        raise ValueError(
            f"Cannot skip onboarding steps. Current='{current}', requested='{target_step}'."
        )

    # tgt_i == cur_i → nothing to do; evaluate() already wrote any advance.
    await db.commit()
    await db.refresh(org)
    return org.onboarding_step
