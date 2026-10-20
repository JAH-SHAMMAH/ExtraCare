"""Which sidebar report section a school section belongs to.

~~~ THE BUG THIS REPLACES ~~~
The sidebar decided this in the browser by comparing a section's NAME against
three literals:

    { "Nursery": "nursery-report", "Primary": "primary-report",
      "Secondary": "secondary-report" }

Fairview's EYFS section is named **"Early Years"**, not "Nursery". So for every
Early Years teacher the comparison matched nothing, the filter returned false,
and the Nursery report section was HIDDEN from the only people who teach in it.
Permission was never the problem — she could open every page in that section by
URL. She just could not find one.

Primary and Secondary matched only because those two names happened to agree
with the literals. A rename in Report Setup would have silently hidden them too,
which is the same defect waiting for a different day.

~~~ WHY THIS LIVES ON THE SERVER ~~~
Deciding it by ID needs the org's WHOLE section list, because "junior" and
"senior" are *relative*: a brief for one section cannot say whether it is the
junior one. The browser cannot get that list for free — `GET /sections` is gated
on `school:read`, which a student does not hold, so resolving client-side would
either cost a request that 403s for students (hiding the section from them
instead) or fall back to the name comparison this module exists to delete.

Resolved once here, attached to each `SectionBrief`, and compared as an opaque
string by the client. No name comparison survives anywhere on the path.

~~~ FAILING OPEN IS DELIBERATE ~~~
A section that cannot be classified is returned with NO report key, and the
sidebar then shows every report section rather than none. The fault being fixed
is a lockout; a resolution gap must not reproduce it in a new shape. Showing one
report section too many is noise, and showing none is the bug.
"""
from __future__ import annotations

from typing import Iterable

NURSERY = "nursery-report"
JUNIOR = "junior-report"
SECONDARY = "secondary-report"

#: Order the sidebar lists them in: senior first, as Educare does.
REPORT_KEYS = (SECONDARY, JUNIOR, NURSERY)


def report_keys_for(sections: Iterable) -> dict[str, str]:
    """Map section id -> report key for every section that classifies.

    EYFS is identified by ``curriculum``, never by name — the convention already
    used by ``seed_domains`` and the report-config bootstrap, whose own comment
    reads "EYFS detection keys on curriculum, not name". It is the one section
    whose identity does not depend on its neighbours.

    The rest are ordered by ``position`` (then name, so the order is total and
    stable rather than dependent on row order): lowest is the junior school,
    highest the senior one. Anything between them is left unmapped, as is a
    school with fewer than two non-EYFS sections — in both cases the answer is
    genuinely unknown, and an unmapped section fails open at the client.
    """
    sections = list(sections)
    out: dict[str, str] = {}

    rest = []
    for s in sections:
        if (getattr(s, "curriculum", "") or "").strip().casefold() == "eyfs":
            out[s.id] = NURSERY
        else:
            rest.append(s)

    # Junior and senior are relative, so they need at least two to compare.
    if len(rest) >= 2:
        rest.sort(key=lambda s: (getattr(s, "position", 0) or 0, (s.name or "").casefold()))
        out[rest[0].id] = JUNIOR
        out[rest[-1].id] = SECONDARY

    return out


#: Words in a free-text department ("Primary", "Secondary Dept", "Early Years")
#: that point at one of the report levels. A fallback after the section NAME.
DEPT_WORDS: dict[str, tuple[str, ...]] = {
    SECONDARY: ("secondary", "senior", "high school", "college"),
    JUNIOR: ("primary", "junior", "basic"),
    NURSERY: ("nursery", "early years", "eyfs", "playgroup", "kindergarten", "creche"),
}


def sections_for_department(department: str | None, sections: Iterable,
                            report_keys: dict[str, str]) -> list:
    """The sections a free-text department names.

    A section's own name wins ("Primary" -> Primary, "Early Years" -> Early
    Years, "Secondary Department" -> Secondary). Only when no name fits do level
    keywords decide, so "Junior School" still finds the Primary row. Returns []
    when nothing fits — callers decide whether that is an error or "unfiltered".
    """
    dept = (department or "").strip().lower()
    if not dept:
        return []
    every = list(sections)
    named = [s for s in every if (s.name or "").strip() and (s.name or "").strip().lower() in dept]
    if named:
        return named
    return [s for s in every
            if any(w in dept for w in DEPT_WORDS.get(report_keys.get(s.id, ""), ()))]
