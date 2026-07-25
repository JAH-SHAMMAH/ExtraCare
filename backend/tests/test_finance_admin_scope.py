"""RBAC restructure: Super User is a real top tier, and sensitive back-office
finance (Budget/Payroll/Salary-Advance/Bank-Ledger/Statements/Broad-View/Reports/
Pay-Adjustments) is gated on the dedicated `finance_admin` namespace — NOT on the
`payments:*` fees scope that org_admin/manager/cashier/parent hold. Plus the
role-assignment escalation guard that makes the separation unbypassable."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import (
    PermissionChecker, assert_can_grant_roles, assert_can_manage_user,
)
from app.routers.modules import finance, finance_ops


# ── Endpoint wiring: which permission gates each finance route ────────────────────

def _route_perms(router) -> dict[tuple[str, str], set[str]]:
    out: dict[tuple[str, str], set[str]] = {}
    for r in getattr(router, "routes", []):
        path = r.path[len("/finance"):] if r.path.startswith("/finance") else r.path
        perms = {
            dep.dependency.permission
            for dep in getattr(r, "dependencies", [])
            if isinstance(getattr(dep, "dependency", None), PermissionChecker)
        }
        for m in (r.methods or []):
            out[(m, path)] = perms
    return out


_SENSITIVE = ("/accounts", "/periods", "/journal", "/statements", "/broad-view",
              "/reports/income-expense", "/payroll", "/salary-advances",
              "/pay-adjustments", "/budgets")


def test_sensitive_finance_routes_gated_on_finance_admin():
    perms = _route_perms(finance.router) | _route_perms(finance_ops.router)

    # Every sensitive route requires finance_admin:* and NEVER a payments:* gate.
    for (method, path), gates in perms.items():
        if not gates:
            continue
        if any(path.startswith(p) for p in _SENSITIVE):
            assert all(g.startswith("finance_admin:") for g in gates), f"{method} {path} → {gates}"
            assert not any(g.startswith("payments:") for g in gates), f"{method} {path} still on payments: {gates}"

    # Representative CRUD split preserved.
    assert perms[("GET", "/budgets")] == {"finance_admin:read"}
    assert perms[("POST", "/budgets")] == {"finance_admin:write"}
    assert perms[("GET", "/payroll")] == {"finance_admin:read"}
    assert perms[("POST", "/payroll")] == {"finance_admin:write"}
    assert perms[("POST", "/payroll/{run_id}/approve")] == {"finance_admin:post"}
    assert perms[("GET", "/accounts")] == {"finance_admin:read"}
    assert perms[("GET", "/statements")] == {"finance_admin:read"}      # report → read-only
    assert perms[("GET", "/broad-view/dashboard")] == {"finance_admin:read"}


def test_fee_collection_routes_stay_on_payments():
    perms = _route_perms(finance.router) | _route_perms(finance_ops.router)
    # Fees / treasury / procurement stay on payments:* so managers/cashiers/parents
    # keep the access they need (and per the approved decisions).
    assert perms[("GET", "/invoices")] == {"payments:read"}
    assert perms[("POST", "/invoices/{invoice_id}/post")] == {"payments:post"}
    assert perms[("GET", "/petty-cash")] == {"payments:read"}     # decision: operational
    assert perms[("GET", "/cash")] == {"payments:read"}           # decision: operational
    assert perms[("POST", "/discounts")] == {"payments:write"}    # decision: fee-side
    assert perms[("GET", "/requisitions")] == {"payments:read"}
    assert perms[("POST", "/bank-accounts")] == {"payments:write"}


# ── Role × finance_admin access matrix ───────────────────────────────────────────

def _user(perms, *, superadmin=False) -> User:
    u = User(id=str(uuid.uuid4()), email=f"u-{uuid.uuid4().hex[:6]}@x.com", full_name="U",
             status=UserStatus.ACTIVE, org_id="o", is_superadmin=superadmin)
    u.roles = [Role(id=str(uuid.uuid4()), name="R", slug="r", permissions=list(perms), org_id="o", is_system=True)]
    return u


def test_finance_admin_access_matrix():
    P = SCHOOL_PERMISSION_PRESETS
    su = _user(P["super_user"])          # ['*']
    acct = _user(P["accountant"])
    hoa = _user(P["head_of_administration"])
    admin = _user(P["org_admin"])
    mgr = _user(P["manager"])
    parent = _user(P["parent"])
    cashier = _user(P["cashier"])

    # Super User + Accountant → full finance_admin (read/write/post).
    for u in (su, acct):
        assert u.has_permission("finance_admin:read")
        assert u.has_permission("finance_admin:write")
        assert u.has_permission("finance_admin:post")

    # Head of Administration → read/write, but NOT post (approvals stay elsewhere).
    assert hoa.has_permission("finance_admin:read") and hoa.has_permission("finance_admin:write")
    assert not hoa.has_permission("finance_admin:post")

    # Admin / Manager / Parent / Cashier → NO sensitive finance at all. This is the
    # whole point: they hold payments:* (fees) but the ledger/budget/payroll is shut.
    for u in (admin, mgr, parent, cashier):
        assert not u.has_permission("finance_admin:read")
        assert not u.has_permission("finance_admin:write")
        assert not u.has_permission("finance_admin:post")

    # …but Admin/Manager keep fee collection, and Super User sits above everything.
    assert admin.has_permission("payments:write") and mgr.has_permission("payments:write")
    assert su.has_permission("payments:write") and su.has_permission("school:students:read")


# ── Escalation guard: can't grant/manage beyond your own tier ─────────────────────

def _role(slug) -> Role:
    return Role(id=str(uuid.uuid4()), name=slug, slug=slug,
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id="o", is_system=True)


def test_grant_guard_blocks_admin_from_elevating():
    admin = _user(SCHOOL_PERMISSION_PRESETS["org_admin"])
    su = _user(SCHOOL_PERMISSION_PRESETS["super_user"])

    # Admin cannot grant Super User (holds `*`) nor finance roles (hold finance_admin).
    for slug in ("super_user", "accountant", "head_of_administration"):
        with pytest.raises(HTTPException) as exc:
            assert_can_grant_roles(admin, [_role(slug)])
        assert exc.value.status_code == 403

    # Admin CAN grant roles wholly within its own permissions.
    assert_can_grant_roles(admin, [_role("manager"), _role("teacher"), _role("cashier")])

    # Super User (`*`) can grant anything.
    assert_can_grant_roles(su, [_role("super_user"), _role("accountant")])


def test_manage_guard_blocks_admin_touching_higher_tier():
    admin = _user(SCHOOL_PERMISSION_PRESETS["org_admin"])
    su = _user(SCHOOL_PERMISSION_PRESETS["super_user"])

    target_super = User(id=str(uuid.uuid4()), email="t@x.com", full_name="T",
                        status=UserStatus.ACTIVE, org_id="o", is_superadmin=False)
    target_super.roles = [_role("super_user")]
    target_mgr = User(id=str(uuid.uuid4()), email="m@x.com", full_name="M",
                      status=UserStatus.ACTIVE, org_id="o", is_superadmin=False)
    target_mgr.roles = [_role("manager")]

    # Admin cannot manage a Super User account; can manage a Manager account.
    with pytest.raises(HTTPException) as exc:
        assert_can_manage_user(admin, target_super)
    assert exc.value.status_code == 403
    assert_can_manage_user(admin, target_mgr)

    # Super User can manage anyone; anyone can manage their own account.
    assert_can_manage_user(su, target_super)
    assert_can_manage_user(admin, admin)
