"""
Structured event logging
=========================
Single-line key=value events for cheap grepping today and easy promotion to
metrics later (each `event=` name maps to a counter; the kv fields become
labels/dimensions). All events go through one helper so the schema stays
consistent.

Usage:
    log_event("school_context_resolved", org_id=..., student=True, teacher=False)
"""

import logging

logger = logging.getLogger("extracare.events")


def log_event(event: str, **fields) -> None:
    """Emit a structured event. Field values are coerced to str for the message
    line; the original dict is also attached via `extra` so a JSON formatter
    can pick it up unchanged when we wire one up."""
    pairs = " ".join(f"{k}={_fmt(v)}" for k, v in fields.items())
    logger.info(f"event={event} {pairs}".strip(), extra={"event": event, **fields})


def _fmt(v) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v)
    return f'"{s}"' if " " in s else s
