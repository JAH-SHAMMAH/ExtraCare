#!/usr/bin/env python
"""Verify all 6 reports endpoints are registered in FastAPI."""

from app.main import app

# List all routes
print("=" * 80)
print("Registered Endpoints in app/routers/modules/reports.py")
print("=" * 80)
print()

reports_routes = [r for r in app.routes if '/reports' in r.path]

for route in sorted(reports_routes, key=lambda r: r.path):
    methods = getattr(route, 'methods', {'GET'})
    methods_str = ', '.join(sorted(methods - {'HEAD', 'OPTIONS'}))
    print(f"{methods_str:6} {route.path}")

print()
print(f"Total reports routes: {len(reports_routes)}")
print()

# Verify the 6 expected endpoints
expected = {
    "GET /api/v1/reports/domains",
    "POST /api/v1/reports/domains",
    "PUT /api/v1/reports/domains/{domain_id}",
    "DELETE /api/v1/reports/domains/{domain_id}",
    "GET /api/v1/reports/students/{student_id}/domain-ratings",
    "POST /api/v1/reports/students/{student_id}/domain-ratings/bulk",
}

actual = set()
for route in reports_routes:
    methods = getattr(route, 'methods', {'GET'})
    for method in sorted(methods - {'HEAD', 'OPTIONS'}):
        actual.add(f"{method} {route.path}")

print("Expected endpoints:")
for ep in sorted(expected):
    status = "[+]" if ep in actual else "[x]"
    print(f"  {status} {ep}")

print()
if expected == actual:
    print("[OK] All 6 endpoints registered correctly!")
    exit(0)
else:
    missing = expected - actual
    extra = actual - expected
    if missing:
        print(f"[ERROR] Missing: {missing}")
    if extra:
        print(f"[WARNING] Extra: {extra}")
    exit(1)
