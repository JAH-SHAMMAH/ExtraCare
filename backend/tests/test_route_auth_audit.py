"""Every API route must sit behind an auth/permission dependency, except this short,
reviewed list. A new route that forgets its dependency fails here instead of shipping.

Reviewed exceptions: login/refresh/logout/register (register is refused outright in
single-school mode), the health probes, payment-provider webhooks (each verifies the
provider's signature or re-checks with the provider), and the biometric device
endpoints (authenticated by a per-device token, not a user session)."""
from fastapi.routing import APIRoute
from app.main import app

ALLOWED_OPEN = {
    ("GET", "/"), ("GET", "/health"),
    ("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/refresh"), ("POST", "/api/v1/auth/register"),
    ("GET", "/api/v1/biometric/commands/pending"),
    ("POST", "/api/v1/biometric/commands/{command_id}/ack"),
    ("POST", "/api/v1/biometric/ingest"),
    ("POST", "/api/v1/payments/fees/webhook/flutterwave"),
    ("POST", "/api/v1/payments/fees/webhook/paystack"),
    ("POST", "/api/v1/payments/remita/webhook"),
}


def _names(dep, acc):
    for s in dep.dependencies:
        c = s.call
        acc.add(getattr(c, "__qualname__", None) or type(c).__name__)
        acc.add(type(c).__name__)
        _names(s, acc)
    return acc


def test_every_route_is_authenticated_or_reviewed():
    open_routes = set()
    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue
        names = _names(r.dependant, set())
        if not any(("current" in x.lower() and "user" in x.lower()) or "Checker" in x or "require" in x.lower() for x in names):
            for m in r.methods:
                open_routes.add((m, r.path))
    assert open_routes - ALLOWED_OPEN == set(), f"unauthenticated routes not on the reviewed list: {sorted(open_routes - ALLOWED_OPEN)}"
