"""Class position, in one place.

~~~ WHAT THIS REPLACES ~~~
Three implementations, disagreeing in two different ways:

  * `report_broadsheet`  sorted by TOTAL and numbered the rows 1..n
  * `report_card`        sorted classmates by TOTAL and took the index
  * `order_of_merit`     ranked by AVERAGE, with STANDARD COMPETITION ranking
                         (1, 2, 2, 4)

So a pupil's position on their own card could differ from their position on the
broadsheet for the same class and term, and differ again on the Order of Merit.

~~~ DENSE, AND BY AVERAGE ~~~
Educare's own cards settle both questions. On the Secondary report two pupils
tie at 888.00 / 88.80 and BOTH print "5th", and the next distinct average
prints "6th" — no gap after the tie. That is dense ranking (1, 2, 2, 3), not
competition ranking, which would have printed "7th".

`order_of_merit` anticipated exactly this. Its docstring read: "Educare's own
convention is unverified; if it uses dense ranking (1, 2, 2, 3) this is the one
place to change." It is no longer unverified, and this is now that one place.

RANKED ON THE AVERAGE, not the total. A total is only comparable between pupils
who sat the same number of subjects; a pupil taking nine subjects would outrank
a pupil taking seven on identical performance. The average is already what the
card prints as the pupil's headline figure, so ranking on it also means the
printed number and the printed position cannot contradict each other.

~~~ COMPARED AT THE PRINTED PRECISION ~~~
Two averages that both PRINT as 88.80 must tie, so the comparison happens on
the rounded value, via `round_dp` — the project's Decimal rounding, never
python's `round()`, which is banker's rounding on floats and would make
88.805 and 88.815 disagree about their own last digit. Ranking on the raw value
instead would print two identical numbers in positions 5 and 6, which is the
exact thing a parent queries.

~~~ AN UNMARKED PUPIL IS NOT RANKED ~~~
They are omitted from the result rather than placed last. Their standing is
unknown, not bottom, and a merit list that placed them would be inventing a
result for a child. Callers treat a missing key as position 0, which is what
both `BroadsheetRow.position` and the card already default to.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Hashable, Mapping, TypeVar

from app.services.report_engine import round_dp

K = TypeVar("K", bound=Hashable)

#: Decimal places the report prints an average to, and therefore the precision
#: at which two averages count as equal.
PLACES = 2


def dense_positions(values: Mapping[K, Decimal | None],
                    *, places: int = PLACES) -> dict[K, int]:
    """Dense positions by value, best first. 1, 2, 2, 3 — no gap after a tie.

    Keys whose value is None are OMITTED from the result, not ranked last.

    The comparison is on `round_dp(value, places)`, so two values that print the
    same tie. Ordering within a tie is irrelevant to the number returned, so no
    tie-break is applied here; a caller that also needs a stable row ORDER sorts
    its own rows.
    """
    marked = [(k, round_dp(v, places)) for k, v in values.items() if v is not None]
    if not marked:
        return {}

    marked.sort(key=lambda kv: kv[1], reverse=True)

    out: dict[K, int] = {}
    position = 0
    previous: Decimal | None = None
    for key, rounded in marked:
        if previous is None or rounded != previous:
            position += 1           # dense: the next DISTINCT value, not the next row
            previous = rounded
        out[key] = position
    return out


def position_of(key: K, values: Mapping[K, Decimal | None],
                *, places: int = PLACES) -> int:
    """One key's dense position, or 0 when it is unmarked or absent.

    0 rather than None because that is what the schemas already default
    `position` to, so an unranked pupil needs no new representation.
    """
    return dense_positions(values, places=places).get(key, 0)


def tied_positions(positions: Mapping[K, int]) -> set[int]:
    """Positions shared by more than one key.

    The Order of Merit flags a shared position so the reader can see that two
    pupils genuinely drew, rather than wondering which of 5th and 6th is which.
    """
    seen: dict[int, int] = {}
    for p in positions.values():
        seen[p] = seen.get(p, 0) + 1
    return {p for p, n in seen.items() if n > 1}
