"""Every dashboard home tile must point somewhere its role can actually reach.

The gap this closes: the sidebar and RouteGuard both read frontend/lib/access.ts,
so they can never disagree. The per-role dashboards are a THIRD consumer that
links with HARDCODED hrefs which nothing governs. Narrow a role's scope and the
sidebar quietly stops showing the staff page, while the home tile keeps pointing
at it and starts returning the "no permission" panel.

That has broken a link three times:
  • payments:read -> payments:own:read  (mig 123)  parent Fees tiles
  • the student narrowing              (mig 121)  student CBT tile
  • attendance :read vs :write                    parent Attendance tiles

Each was found by a person clicking it. This finds it in CI instead.

Why this lives in the BACKEND suite rather than with the vitest tests: the role
presets are defined here, in Python. The existing frontend access test mirrors
one preset by hand and needs a second backend test to police the copy — fine for
one role, but four roles of duplication would rot faster than it catches
anything. Importing SCHOOL_PERMISSION_PRESETS directly means there is no copy.
The frontend files are read as text, which needs no JS toolchain.

Limits worth knowing:
  • Only literal `href="/dashboard/..."` is checked. A computed href
    (href={`/x/${id}`}) is invisible here.
  • `permissionAllowedForOrg` (plan/feature gating) is not modelled, so a tile
    this test passes could still be hidden by a tenant's disabled module. That
    makes the test permissive, never falsely strict.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.models.role import SCHOOL_PERMISSION_PRESETS

# backend/tests/ -> backend/ -> repo root
REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"
ACCESS_TS = FRONTEND / "lib" / "access.ts"
HOME_DIR = FRONTEND / "app" / "(dashboard)" / "dashboard" / "home"

# Which role sees which home, from dashboard/page.tsx's switch on activeRole.
# "admin" and every non-school context fall through to AdminHome; org_admin is
# the representative admin preset.
HOMES = {
    "ParentHome.tsx": "parent",
    "StudentHome.tsx": "student",
    "TeacherHome.tsx": "teacher",
    "AdminHome.tsx": "org_admin",
}

pytestmark = pytest.mark.skipif(
    not ACCESS_TS.exists() or not HOME_DIR.exists(),
    reason="frontend/ not present in this checkout — nothing to cross-check",
)


# ── mirrors of the frontend, kept deliberately literal ────────────────────────

def _route_rules() -> list[tuple[str, str, list[str]]]:
    """(prefix, permission, anyOf) parsed out of ROUTE_ACCESS in access.ts.

    Read as text rather than executed: this is the only way to reach a TS
    constant from Python, and the shape is stable enough to parse safely. If the
    parse ever finds nothing, the test fails loudly rather than passing vacuously
    (see test_the_access_map_parsed).
    """
    src = ACCESS_TS.read_text(encoding="utf-8")
    rules: list[tuple[str, str, list[str]]] = []
    # One object literal per entry; no nested braces inside them.
    for block in re.findall(r"\{[^{}]*?prefix:\s*\"[^\"]+\"[^{}]*?\}", src, re.S):
        prefix = re.search(r'prefix:\s*"([^"]+)"', block)
        perm = re.search(r'permission:\s*"([^"]+)"', block)
        if not prefix or not perm:
            continue
        any_of_raw = re.search(r"anyOf:\s*\[([^\]]*)\]", block)
        any_of = re.findall(r'"([^"]+)"', any_of_raw.group(1)) if any_of_raw else []
        rules.append((prefix.group(1), perm.group(1), any_of))
    return rules


def _match_route(path: str, rules):
    """Longest matching prefix wins — matchRoute() in access.ts."""
    best = None
    for prefix, perm, any_of in rules:
        if path == prefix or path.startswith(prefix + "/"):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, perm, any_of)
    return best


def _has_permission(perms: set[str], permission: str) -> bool:
    """Mirrors useAuthStore.hasPermission, including the scope hierarchy."""
    if "*" in perms or permission in perms:
        return True
    parts = permission.split(":")
    if f"{parts[0]}:*" in perms:
        return True
    # A broad two-part grant covers its fine-grained child:
    # "school:read" satisfies "school:students:read".
    if len(parts) == 3 and f"{parts[0]}:{parts[2]}" in perms:
        return True
    return False


def _can_access(path: str, perms: set[str], rules) -> bool:
    """canAccessPath(): an unmapped route is open; anyOf is OR semantics."""
    best = _match_route(path, rules)
    if best is None:
        return True
    _, permission, any_of = best
    if any_of:
        return _has_permission(perms, permission) or any(
            _has_permission(perms, a) for a in any_of
        )
    return _has_permission(perms, permission)


def _hrefs(component: str) -> list[str]:
    src = (HOME_DIR / component).read_text(encoding="utf-8")
    return sorted(set(re.findall(r'href="(/dashboard[^"]*)"', src)))


# ── the guards on the checker itself ──────────────────────────────────────────

def test_the_access_map_parsed():
    """A regex that silently matched nothing would make every case below pass."""
    rules = _route_rules()
    assert len(rules) > 100, f"only parsed {len(rules)} route rules — regex broken?"
    by_prefix = {p: (perm, a) for p, perm, a in rules}
    # Spot-check entries whose values this suite reasons about.
    assert by_prefix["/dashboard/modules/school/grades"][0] == "school:grades:read"
    assert by_prefix["/dashboard/modules/school/fees"][0] == "payments:read"
    # And that anyOf survives the parse.
    assert by_prefix["/dashboard/modules/school/store-pickup"][1] == ["store:sell"]


@pytest.mark.parametrize("component", sorted(HOMES))
def test_every_home_component_has_links(component):
    """If a rename empties this list the coverage vanishes silently."""
    assert _hrefs(component), f"no literal hrefs found in {component}"


def test_the_checker_would_catch_a_regression():
    """The bug this suite exists for, asserted directly: a parent pointed at the
    staff fees page must be reported as unreachable."""
    rules = _route_rules()
    parent = set(SCHOOL_PERMISSION_PRESETS["parent"])
    assert not _can_access("/dashboard/modules/school/fees", parent, rules)
    assert not _can_access("/dashboard/modules/school/grades", parent, rules)
    # …while the route it was repointed to is reachable.
    assert _can_access("/dashboard/my-children/payments", parent, rules)


# ── the invariant ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("component,role", sorted(HOMES.items()))
def test_every_dashboard_tile_is_reachable_by_its_role(component, role):
    rules = _route_rules()
    perms = set(SCHOOL_PERMISSION_PRESETS[role])
    blocked = []
    for href in _hrefs(component):
        if not _can_access(href, perms, rules):
            best = _match_route(href, rules)
            blocked.append(f"{href} (needs {best[1] if best else '?'})")
    assert not blocked, (
        f"{component} links to {len(blocked)} route(s) the '{role}' role cannot "
        f"reach, so the tile returns RouteGuard's 'no permission' panel:\n  "
        + "\n  ".join(blocked)
        + f"\n\nPoint them at routes this role's sidebar already shows it "
        f"(the /dashboard/my-* pages for parent/student), or widen the role. "
        f"See the note in frontend/lib/access.ts."
    )
