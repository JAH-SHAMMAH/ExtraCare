"""Teacher role RBAC — the classroom tier must not reach admin surfaces.

Context: the teacher preset used to carry the BROAD `school:read` + `school:write`.
Because the scope hierarchy makes a two-part grant cover every three-part child
(User.has_permission), that single grant reached school:students:write,
school:admissions:write, school:timetable:write, school:library:write … i.e. a
teacher could delete a pupil, run promotions, edit the timetable structure and
administer Voting. This suite pins the narrowed preset.

The route test walks the REAL FastAPI app and reads each route's
PermissionChecker, so a future endpoint added to an admin module on a
classroom-tier scope fails here rather than in production.
"""
from __future__ import annotations

import uuid

import pytest

from app.core.permissions import AnyPermissionChecker, PermissionChecker
from app.main import app
from app.models.role import Role, permission_presets_for_industry
from app.models.user import User, UserStatus


TEACHER_PERMS = permission_presets_for_industry("school")["teacher"]


def _teacher() -> User:
    """A user holding exactly the shipped teacher preset."""
    u = User(id=str(uuid.uuid4()), email="teacher@fairviewschoolng.com", full_name="Class Teacher",
             status=UserStatus.ACTIVE, org_id="org-1")
    u.roles = [Role(id=str(uuid.uuid4()), org_id="org-1", name="Teacher", slug="teacher",
                    permissions=list(TEACHER_PERMS))]
    return u


# Scopes an admin/HR surface is gated on. A teacher must hold NONE of these.
FORBIDDEN = [
    "school:read", "school:write",                       # the broad grants themselves
    "school:students:write",                             # create/withdraw/delete pupil, promotion, transfer
    "school:admissions:read", "school:admissions:write",  # admissions, entrance exams, acceptance
    "school:timetable:write",                            # timetable structure
    "school:library:read", "school:library:write",       # library administration
    "school:parents:read", "school:parents:write",       # guardian PII
    "school:hostel:read", "school:hostel:write",         # boarding cluster + exeat
    "school:subjects:write", "school:classes:write",     # academic taxonomy
    "school_admin:read", "school_admin:write",           # SMS/transport/tuckshop/ratings/staff
    "school_admin:facility:read",
    "settings:read", "settings:write",                   # every Setup hub
    "users:write", "roles:write", "audit_logs:read",
    "hr:write", "analytics:read",
    "payments:read", "payments:write", "finance_admin:read", "medical:read",
]

# Scopes the classroom tier legitimately needs.
ALLOWED = [
    "users:read", "hr:read",
    "school:classes:read", "school:teachers:read", "school:students:read",
    "school:subjects:read", "school:timetable:read",
    "school:grades:read", "school:grades:write",
    "school:exams:read", "school:exams:write",
    "school:reports:read", "school:reports:write",
    "school:attendance:read", "school:attendance:write",
    "school:lessons:read", "school:lessons:write",
    "school:cbt:read", "school:cbt:write", "school:cbt:manage",
    "school:classroom:read", "school:classroom:write", "school:classroom:manage",
    "school:pastoral:read",
    "school:behaviour:read", "school:behaviour:write",
    "school:journals:read", "school:journals:write",
    "school:feedback:read", "school:feedback:write",
    "school:clubs:read", "school:clubs:write",
    "school:calendar:read", "school:calendar:write",
]


@pytest.mark.parametrize("permission", FORBIDDEN)
def test_teacher_is_denied_admin_scopes(permission):
    assert not _teacher().has_permission(permission), (
        f"teacher unexpectedly holds {permission!r} — check the preset in models/role.py"
    )


@pytest.mark.parametrize("permission", ALLOWED)
def test_teacher_keeps_classroom_scopes(permission):
    assert _teacher().has_permission(permission), (
        f"teacher lost {permission!r} — a classroom surface will 403"
    )


def test_every_teaching_role_uses_the_narrowed_tier():
    """_TCH is shared by the whole teaching catalogue; none may keep the broad grant."""
    presets = permission_presets_for_industry("school")
    for slug in ("teacher", "instructor", "head_teacher", "academic_coordinator",
                 "head_of_department_secondary", "head_of_early_years",
                 "homeroom_coordinator", "exam_subject_head", "spa_officer", "spa_manager"):
        assert "school:write" not in presets[slug], f"{slug} still holds the broad school:write"
        assert "school:read" not in presets[slug], f"{slug} still holds the broad school:read"


def _route_permissions(route) -> list[list[str]]:
    """Each permission gate on `route`, as a list of accepted-scope alternatives."""
    gates: list[list[str]] = []
    for dep in getattr(getattr(route, "dependant", None), "dependencies", []) or []:
        call = getattr(dep, "call", None)
        if isinstance(call, PermissionChecker):
            gates.append([call.permission])
        elif isinstance(call, AnyPermissionChecker):
            gates.append(list(call.permissions))
    return gates


def _teacher_can_reach(route) -> bool:
    """True if the teacher preset satisfies EVERY permission gate on the route."""
    gates = _route_permissions(route)
    if not gates:
        return False        # ungated routes are not part of this assertion
    user = _teacher()
    return all(any(user.has_permission(p) for p in gate) for gate in gates)


# (path fragment, HTTP methods) that must be unreachable for a teacher. These are
# the surfaces the Educare benchmark keeps strictly admin-side.
ADMIN_ROUTES = [
    ("/school/students", {"POST", "PATCH", "DELETE"}),   # roster CRUD incl. withdraw/delete
    ("/enrollment/promotions", {"POST", "GET"}),         # admissions router is mounted at /enrollment
    ("/enrollment/transfers", {"POST", "PATCH", "GET"}),
    ("/timetable/periods", {"POST", "PATCH", "DELETE"}),
    ("/timetable/schedules", {"POST", "PATCH", "DELETE"}),
    ("/voting/", {"POST", "PATCH", "DELETE"}),
    ("/library/", {"POST", "PATCH", "DELETE"}),
]


@pytest.mark.parametrize("fragment,methods", ADMIN_ROUTES)
def test_admin_routes_are_unreachable_by_teacher(fragment, methods):
    checked = 0
    for route in app.routes:
        path, route_methods = getattr(route, "path", ""), getattr(route, "methods", set()) or set()
        if fragment not in path or not (route_methods & methods):
            continue
        checked += 1
        assert not _teacher_can_reach(route), (
            f"teacher can call {sorted(route_methods & methods)} {path} — "
            "it is gated on a scope the classroom tier holds"
        )
    assert checked, f"no routes matched {fragment!r} — the fragment is stale"


def _student() -> User:
    presets = permission_presets_for_industry("school")
    u = User(id=str(uuid.uuid4()), email="pupil@fairviewschoolng.com", full_name="Pupil",
             status=UserStatus.ACTIVE, org_id="org-1")
    u.roles = [Role(id=str(uuid.uuid4()), org_id="org-1", name="Student", slug="student",
                    permissions=list(presets["student"]))]
    return u


def test_students_cannot_administer_eclassroom_schedules():
    """Regression guard: students hold school:classroom:write (they submit classwork).

    The eClassroom schedule cluster must therefore NOT ride that scope, or pupils
    would gain create/delete/go-live on the school's virtual classrooms. It uses the
    staff-only school:classroom:manage instead.
    """
    student, checked = _student(), 0
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if "/eclassroom/schedules" not in path or not (methods & {"POST", "PATCH", "DELETE"}):
            continue
        checked += 1
        gates = _route_permissions(route)
        assert gates and not all(any(student.has_permission(p) for p in gate) for gate in gates), (
            f"student can call {sorted(methods)} {path}"
        )
    assert checked, "no eClassroom schedule write routes found — the path is stale"


def test_teacher_keeps_the_report_pipeline():
    """The T-1 teacher report surfaces must still be reachable after narrowing."""
    wanted = {"/api/v1/platform/report-entry", "/api/v1/platform/my-teaching-assignments",
              "/api/v1/platform/report-broadsheet", "/api/v1/platform/report-card"}
    seen = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if path in wanted and "GET" in (getattr(route, "methods", set()) or set()):
            seen.add(path)
            assert _teacher_can_reach(route), f"teacher lost {path} — Make Report / Reports View will 403"
    assert seen == wanted, f"routes missing from the app: {wanted - seen}"
