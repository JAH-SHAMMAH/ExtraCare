"""Every /finance and /payments route, hit as the people who must NOT reach it.

A teacher, a student and a parent get 401/403 on every finance route, except the few
that are deliberately theirs (listed). Catches a new route added without a permission."""
import re
import pytest
from app.main import app
from tests.test_result_flow_e2e import API, _h, _user, http, world  # noqa: F401

pytestmark = pytest.mark.asyncio

# (method, path-prefix) reachable by a PARENT on purpose.
PARENT_OK = ("/payments/fees/", "/payments/remita/invoices", "/payments/remita/initiate", "/payments/remita/verify",
             "/finance/bank-accounts/primary", "/finance/fee-records/mine", "/finance/wallet")
# Provider -> server callbacks authenticate by signature, not by user.
CALLBACKS = ("/payments/fees/webhook/", "/payments/remita/webhook")


def _routes():
    out = []
    for r in app.routes:
        path = getattr(r, "path", "")
        if not path.startswith("/api/v1/finance") and not path.startswith("/api/v1/payments"):
            continue
        for m in getattr(r, "methods", set()) - {"HEAD", "OPTIONS"}:
            out.append((m, re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)))
    return sorted(set(out))


async def test_non_finance_users_cannot_reach_finance_routes(http, db, org, world):
    student = await _user(db, org, "student", "Pupil")
    cases = {"teacher": _h(world["teacher"]), "student": _h(student)}
    bad = []
    for method, path in _routes():
        rel = path[len("/api/v1"):]
        if rel.startswith(CALLBACKS):
            continue
        for who, h in cases.items():
            r = await http.request(method, path, headers=h, json={} if method != "GET" else None)
            if r.status_code not in (401, 403):
                bad.append((who, method, rel, r.status_code))
    assert not bad, bad[:15]


async def test_parent_only_reaches_their_own_payment_routes(http, db, org, world):
    h = _h(world["parent"])
    bad = []
    for method, path in _routes():
        rel = path[len("/api/v1"):]
        if rel.startswith(CALLBACKS) or rel.startswith(PARENT_OK):
            continue
        r = await http.request(method, path, headers=h, json={} if method != "GET" else None)
        if r.status_code not in (401, 403):
            bad.append((method, rel, r.status_code))
    assert not bad, bad[:15]


async def test_unauthenticated_cannot_reach_finance_routes(http, world):
    bad = []
    for method, path in _routes():
        rel = path[len("/api/v1"):]
        if rel.startswith(CALLBACKS):
            continue
        r = await http.request(method, path, json={} if method != "GET" else None)
        if r.status_code not in (401, 403):
            bad.append((method, rel, r.status_code))
    assert not bad, bad[:15]
