"""
School module AI handler.

Deterministic templates over caller-supplied context. No DB reads —
the router is responsible for passing the student/class/term fields
it wants summarised. This keeps the assistant safe (no hallucinated
IDs, no cross-tenant leakage via clever prompts) and cheap.

Supported tasks:
  • generate_report   — per-student report-card summary
  • summarise         — free-form digest over provided bullets/text
  • suggest           — short, actionable nudge for a teacher/admin

Unknown tasks raise ValueError; the router maps that to a 400.
"""

from __future__ import annotations

from typing import Any


SUPPORTED_TASKS = ("generate_report", "summarise", "suggest")


def _student_label(context: dict[str, Any]) -> str:
    name = context.get("student_name") or context.get("name")
    sid = context.get("student_id") or context.get("id")
    if name and sid:
        return f"{name} (#{sid})"
    return name or (f"Student #{sid}" if sid else "the student")


def _generate_report(context: dict[str, Any]) -> str:
    who = _student_label(context)
    term = context.get("term") or "this term"
    avg = context.get("average_score")
    attendance = context.get("attendance_rate")
    strengths = context.get("strengths") or []
    concerns = context.get("concerns") or []

    lines = [f"Report summary for {who} — {term}."]
    if avg is not None:
        lines.append(f"Overall average: {avg}.")
    if attendance is not None:
        lines.append(f"Attendance rate: {attendance}.")
    if strengths:
        lines.append("Strengths: " + ", ".join(str(s) for s in strengths) + ".")
    if concerns:
        lines.append("Areas to watch: " + ", ".join(str(c) for c in concerns) + ".")
    if len(lines) == 1:
        lines.append("No academic data supplied — add scores/attendance to the context for a fuller summary.")
    return " ".join(lines)


def _summarise(context: dict[str, Any]) -> str:
    title = context.get("title") or "Summary"
    points = context.get("points") or context.get("bullets") or []
    text = context.get("text")
    if points:
        body = "; ".join(str(p) for p in points)
        return f"{title}: {body}."
    if text:
        snippet = text.strip().splitlines()[0][:240]
        return f"{title}: {snippet}"
    return f"{title}: no content supplied to summarise."


def _suggest(context: dict[str, Any]) -> str:
    goal = context.get("goal") or "improve outcomes"
    who = _student_label(context) if context.get("student_name") or context.get("student_id") else context.get("audience", "the team")
    return (
        f"Suggestion for {who}: focus on {goal}. "
        "Break it into weekly check-ins, capture one measurable signal, and review progress at the next staff meeting."
    )


_DISPATCH = {
    "generate_report": _generate_report,
    "summarise": _summarise,
    "suggest": _suggest,
}


def handle(task: str, context: dict[str, Any]) -> str:
    fn = _DISPATCH.get(task)
    if fn is None:
        raise ValueError(f"Unsupported school task: {task!r}. Supported: {SUPPORTED_TASKS}")
    return fn(context or {})
