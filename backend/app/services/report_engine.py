"""Cumulative evaluator for the Secondary Report engine (S-4).

Pure functions — no DB, no ORM — so the composition maths is unit-testable in
isolation. The router loads assessments / cumulatives / scores into plain dicts
and calls ``evaluate_cumulative``.

A cumulative's (value, max) is computed from its components (assessments and/or
nested cumulatives):
  • score              → value = Σ component values,  max = Σ component maxes
  • percentage         → value = Σvalues / Σmaxes * 100,          max = 100
  • custom_percentage  → value = Σvalues / Σmaxes * max_percent,  max = max_percent
"""
from __future__ import annotations

from decimal import Decimal


def _d(v) -> Decimal:
    if v is None:
        return Decimal(0)
    return v if isinstance(v, Decimal) else Decimal(str(v))


def evaluate_cumulative(cid, cumulatives, components, assessments, scores, _stack=None):
    """Return ``(value, max)`` as Decimals for cumulative ``cid``.

    cumulatives : {id: obj with .cumul_type, .max_percent}
    components  : {cumulative_id: [(ref_type, ref_id), ...] in order}
    assessments : {id: obj with .max_score}
    scores      : {assessment_id: raw score}  (missing = 0)
    """
    _stack = _stack or set()
    if cid in _stack or cid not in cumulatives:
        return Decimal(0), Decimal(0)            # cycle / dangling guard
    _stack = _stack | {cid}
    c = cumulatives[cid]

    total_val = Decimal(0)
    total_max = Decimal(0)
    for ref_type, ref_id in components.get(cid, []):
        if ref_type == "assessment":
            a = assessments.get(ref_id)
            if not a:
                continue
            v, mx = _d(scores.get(ref_id)), _d(a.max_score)
        else:
            v, mx = evaluate_cumulative(ref_id, cumulatives, components, assessments, scores, _stack)
        total_val += v
        total_max += mx

    ctype = getattr(c, "cumul_type", "score")
    if ctype == "percentage":
        pct = (total_val / total_max * 100) if total_max else Decimal(0)
        return pct, Decimal(100)
    if ctype == "custom_percentage":
        cap = _d(getattr(c, "max_percent", None))
        scaled = (total_val / total_max * cap) if total_max else Decimal(0)
        return scaled, cap
    return total_val, total_max      # score (sum)


def round_dp(value: Decimal, places: int) -> Decimal:
    """Round for display to ``places`` decimals (banker's-safe, ROUND_HALF_UP-ish)."""
    from decimal import ROUND_HALF_UP
    q = Decimal(1).scaleb(-max(int(places), 0))
    return _d(value).quantize(q, rounding=ROUND_HALF_UP)
