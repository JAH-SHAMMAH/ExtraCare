"""Pupils and parents hold feedback/journals/clubs read scopes; the staff-only lists behind
those routes must not be readable with them."""
from __future__ import annotations

import pytest

from app.core.permissions import AnyPermissionChecker, PermissionChecker
from app.models.role import SCHOOL_PERMISSION_PRESETS as P
from app.routers.modules import clubs, feedback, timetable
from app.routers.modules.report_extras import router as extras_router

pytestmark = pytest.mark.asyncio


def _needs(router, path, method="GET"):
    for r in router.routes:
        if getattr(r, "path", None) == path and method in r.methods:
            out = set()
            for d in r.dependencies:
                c = d.dependency
                if isinstance(c, PermissionChecker):
                    out.add(c.permission)
                elif isinstance(c, AnyPermissionChecker):
                    out.update(c.permissions)
            return out
    raise AssertionError(path)


def _passes(role, scopes):
    return any(_has(P[role], s) for s in scopes)


def _has(perms, p):
    if "*" in perms or p in perms:
        return True
    a = p.split(":")
    return len(a) == 3 and f"{a[0]}:{a[2]}" in perms


CASES = [
    (feedback.router, "/feedback/daily-reports"),
    (feedback.router, "/feedback/student-daily-reports"),
    (clubs.router, "/clubs/{club_id}/members"),
    (clubs.router, "/clubs/{club_id}/enrollment-candidates"),
    (timetable.router, "/timetable/subject-attendance"),
]


@pytest.mark.parametrize("router,path", CASES)
async def test_students_and_parents_are_refused(router, path):
    prefix = getattr(router, "prefix", "")
    full = path if path.startswith(prefix) else prefix + path
    need = _needs(router, full)
    assert need, path
    for role in ("student", "parent"):
        assert not _passes(role, need), f"{role} can read {path}"
    assert _passes("teacher", need) or path.startswith("/timetable"), f"teacher lost {path}"
