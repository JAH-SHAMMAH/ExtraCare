"""
Hospital module AI handler.

Same shape as the school handler — deterministic templates over caller
context, no DB reads. Medical copy stays neutral on purpose: the
assistant is a clerical aid, not a diagnostic tool, and the wording
here is what gets shown verbatim to staff.

Supported tasks:
  • summarise_vitals  — one-line digest of provided vitals
  • generate_report   — patient encounter summary
  • suggest           — follow-up nudge (non-clinical)
"""

from __future__ import annotations

from typing import Any


SUPPORTED_TASKS = ("summarise_vitals", "generate_report", "suggest")


def _patient_label(context: dict[str, Any]) -> str:
    name = context.get("patient_name") or context.get("name")
    pid = context.get("patient_id") or context.get("id")
    if name and pid:
        return f"{name} (#{pid})"
    return name or (f"Patient #{pid}" if pid else "the patient")


def _summarise_vitals(context: dict[str, Any]) -> str:
    who = _patient_label(context)
    vitals = context.get("vitals") or {}
    parts: list[str] = []
    for key in ("temperature", "heart_rate", "blood_pressure", "respiratory_rate", "spo2"):
        val = vitals.get(key)
        if val is not None:
            parts.append(f"{key.replace('_', ' ')} {val}")
    if not parts:
        return f"Vitals summary for {who}: no vitals supplied."
    return f"Vitals for {who}: " + ", ".join(parts) + ". Review within the patient's baseline before acting."


def _generate_report(context: dict[str, Any]) -> str:
    who = _patient_label(context)
    visit_date = context.get("visit_date") or "the latest encounter"
    complaint = context.get("complaint") or "unspecified complaint"
    findings = context.get("findings") or []
    plan = context.get("plan") or []

    lines = [f"Encounter summary for {who} on {visit_date}."]
    lines.append(f"Presenting complaint: {complaint}.")
    if findings:
        lines.append("Findings: " + "; ".join(str(f) for f in findings) + ".")
    if plan:
        lines.append("Plan: " + "; ".join(str(p) for p in plan) + ".")
    return " ".join(lines)


def _suggest(context: dict[str, Any]) -> str:
    who = _patient_label(context) if context.get("patient_name") or context.get("patient_id") else "the care team"
    goal = context.get("goal") or "confirm next follow-up"
    return (
        f"Suggestion for {who}: {goal}. "
        "This is an administrative nudge, not a clinical recommendation — verify against the chart before acting."
    )


_DISPATCH = {
    "summarise_vitals": _summarise_vitals,
    "generate_report": _generate_report,
    "suggest": _suggest,
}


def handle(task: str, context: dict[str, Any]) -> str:
    fn = _DISPATCH.get(task)
    if fn is None:
        raise ValueError(f"Unsupported hospital task: {task!r}. Supported: {SUPPORTED_TASKS}")
    return fn(context or {})
