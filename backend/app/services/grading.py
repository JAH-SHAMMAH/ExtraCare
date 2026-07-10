"""Shared grading scale — one letter-grade scheme school-wide.

Both the manual gradebook (school router) and the CBT gradebook feed derive
letters from this single scale, so the same percentage always maps to the same
letter regardless of which subsystem produced the mark. WAEC-style default;
edit GRADING_SCALE to change the boundaries school-wide.
"""
from __future__ import annotations

GRADING_SCALE = [(70, "A"), (60, "B"), (50, "C"), (45, "D"), (40, "E")]  # else "F"


def grade_letter(score: float | None, total: float | None) -> str | None:
    """Letter for score/total, or None when the mark can't be computed."""
    if score is None or not total or total <= 0:
        return None
    pct = (float(score) / float(total)) * 100
    for threshold, letter in GRADING_SCALE:
        if pct >= threshold:
            return letter
    return "F"
