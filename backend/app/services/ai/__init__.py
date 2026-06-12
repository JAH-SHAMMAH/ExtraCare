"""
AI assistant — module-aware dispatch.

The router funnels every request through `dispatch(module, task, context)`.
We keep routing centralised here so new modules plug in with one dict
entry and the router stays free of module-specific branching.

No handler reaches into the DB or global state; the caller must pass
everything the template needs via `context`. This is a hard safety
rule — see docstrings on each handler.
"""

from __future__ import annotations

from typing import Any

from app.services.ai import (
    business_assistant,
    hospital_assistant,
    school_assistant,
)


# Module key → (handler module, supported tasks). Keep the tuple so the
# router can surface the valid task list in 400 responses without
# importing each handler.
_REGISTRY = {
    "school": (school_assistant, school_assistant.SUPPORTED_TASKS),
    "hospital": (hospital_assistant, hospital_assistant.SUPPORTED_TASKS),
    "business": (business_assistant, business_assistant.SUPPORTED_TASKS),
}


SUPPORTED_MODULES = tuple(_REGISTRY.keys())


def supported_tasks(module: str) -> tuple[str, ...]:
    entry = _REGISTRY.get(module)
    return entry[1] if entry else ()


def dispatch(module: str, task: str, context: dict[str, Any] | None) -> str:
    """Route a request to the correct module handler and return its text.

    Raises:
        KeyError  — unknown module (router maps to 400)
        ValueError — unknown task for that module (router maps to 400)
    """
    entry = _REGISTRY.get(module)
    if entry is None:
        raise KeyError(module)
    handler, _ = entry
    return handler.handle(task, context or {})


__all__ = ("dispatch", "supported_tasks", "SUPPORTED_MODULES")
