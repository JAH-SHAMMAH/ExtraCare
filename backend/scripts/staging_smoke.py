"""
Staging smoke test.

Drives a deployed ExtraCare backend through the critical paths and asserts
expected shapes + observable behaviours. Exits non-zero on any failure so it
plugs straight into a deploy pipeline as a post-deploy gate.

Usage:
    BASE_URL=https://staging-api.extracare.app \
    EMAIL=admin@tenant.test PASSWORD=... \
    python scripts/staging_smoke.py

Optional:
    STUDENT_EMAIL=...  STUDENT_PASSWORD=...    # skip student-path checks if unset
    TEACHER_EMAIL=...  TEACHER_PASSWORD=...    # skip teacher-path checks if unset
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import httpx


BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
TIMEOUT = httpx.Timeout(15.0, connect=5.0)

failures: list[str] = []
passes: list[str] = []


def _check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        passes.append(label)
        print(f"  [PASS] {label}")
    else:
        failures.append(f"{label} — {detail}")
        print(f"  [FAIL] {label}: {detail}")


def login(client: httpx.Client, email: str, password: str) -> str | None:
    t0 = time.perf_counter()
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    ms = (time.perf_counter() - t0) * 1000
    print(f"  login {email}: {r.status_code} in {ms:.0f}ms")
    if r.status_code != 200:
        return None
    return r.json().get("access_token")


def as_user(client: httpx.Client, token: str) -> httpx.Client:
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def run_admin_checks(client: httpx.Client) -> None:
    # 1. School context resolves and emits cache header.
    r = client.get("/api/v1/me/school-context")
    _check("me/school-context 200", r.status_code == 200, f"got {r.status_code}")
    _check(
        "me/school-context sets private cache header",
        r.headers.get("cache-control", "").startswith("private"),
        r.headers.get("cache-control", "<none>"),
    )
    if r.status_code == 200:
        body = r.json()
        _check("school-context has user_id", "user_id" in body)

    # 2. Admin sees school-wide feedback (no mine filter).
    r = client.get("/api/v1/feedback", params={"page": 1, "page_size": 10})
    _check("feedback list 200", r.status_code == 200, f"got {r.status_code}")

    # 3. Aggregation endpoints.
    r = client.get("/api/v1/tuckshop/sales/summary")
    _check("tuckshop/sales/summary 200", r.status_code == 200)
    if r.status_code == 200:
        body = r.json()
        for k in ("total_revenue", "total_units", "transactions", "top_products"):
            _check(f"sales summary has '{k}'", k in body)
        _check(
            "sales summary short cache for today",
            r.headers.get("cache-control") == "private, max-age=30",
            r.headers.get("cache-control", "<none>"),
        )

    r = client.get("/api/v1/behaviour/summary")
    _check("behaviour/summary 200", r.status_code == 200)
    if r.status_code == 200:
        body = r.json()
        _check(
            "behaviour breakdown shape",
            set(body.get("breakdown", {}).keys()) == {"positive", "negative", "neutral"},
            str(body.get("breakdown"))[:80],
        )


def run_for_me_checks(client: httpx.Client, role: str) -> None:
    """Exercise the for_me filtering path. Expects authenticated client."""
    for path in [
        "/api/v1/classroom/assignments",
        "/api/v1/cbt/exams",
    ]:
        mine = client.get(path, params={"for_me": "true", "page": 1, "page_size": 5})
        all_ = client.get(path, params={"page": 1, "page_size": 5})
        _check(f"{role}: {path} for_me=true 200", mine.status_code == 200, f"got {mine.status_code}")
        _check(f"{role}: {path} all 200", all_.status_code == 200, f"got {all_.status_code}")
        if mine.status_code == 200 and all_.status_code == 200:
            # mine ⊆ all is the invariant worth checking; also mine should never
            # return a larger set than the unfiltered view.
            mine_n = len(mine.json().get("items", []))
            all_n = len(all_.json().get("items", []))
            _check(
                f"{role}: {path} mine <= all ({mine_n} <= {all_n})",
                mine_n <= all_n,
            )


def run_cbt_live_window_check(client: httpx.Client) -> None:
    """Best-effort: find any exam and attempt to start it. We can't assert
    the exact outcome without knowing the exam window, but we can confirm the
    endpoint is reachable and returns a sensible shape on 400/201."""
    r = client.get("/api/v1/cbt/exams", params={"page": 1, "page_size": 1})
    if r.status_code != 200 or not r.json().get("items"):
        print("  [SKIP] cbt start-attempt: no exams available to probe")
        return
    exam = r.json()["items"][0]
    # Use a fake student_id — we expect this to 404/403 or 400 in normal orgs,
    # which still exercises the live-window handler's rejection path.
    r = client.post(
        f"/api/v1/cbt/exams/{exam['id']}/attempts",
        params={"student_id": "00000000-0000-0000-0000-000000000000"},
    )
    _check(
        "cbt attempt rejection is a structured 4xx",
        400 <= r.status_code < 500,
        f"got {r.status_code}",
    )


def main() -> int:
    if not BASE_URL:
        print("BASE_URL is required (e.g. https://staging-api.extracare.app)")
        return 2

    print(f"Target: {BASE_URL}")

    # Health first — fail fast if the app isn't up.
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
        r = c.get("/health")
        _check("GET /health 200", r.status_code == 200, f"got {r.status_code}")
        if r.status_code == 200:
            _check("/health reports environment", "environment" in r.json())

    # Admin path.
    email = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")
    if email and password:
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
            tok = login(c, email, password)
            _check("admin login succeeded", bool(tok), "no token returned")
            if tok:
                as_user(c, tok)
                run_admin_checks(c)
                run_for_me_checks(c, role="admin")
                run_cbt_live_window_check(c)
    else:
        print("  [SKIP] admin checks (EMAIL/PASSWORD unset)")

    # Teacher path (optional).
    t_email = os.environ.get("TEACHER_EMAIL")
    t_password = os.environ.get("TEACHER_PASSWORD")
    if t_email and t_password:
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
            tok = login(c, t_email, t_password)
            _check("teacher login", bool(tok))
            if tok:
                as_user(c, tok)
                run_for_me_checks(c, role="teacher")
    else:
        print("  [SKIP] teacher checks (TEACHER_EMAIL/TEACHER_PASSWORD unset)")

    # Student path (optional).
    s_email = os.environ.get("STUDENT_EMAIL")
    s_password = os.environ.get("STUDENT_PASSWORD")
    if s_email and s_password:
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
            tok = login(c, s_email, s_password)
            _check("student login", bool(tok))
            if tok:
                as_user(c, tok)
                run_for_me_checks(c, role="student")
    else:
        print("  [SKIP] student checks (STUDENT_EMAIL/STUDENT_PASSWORD unset)")

    print()
    print(f"PASSED: {len(passes)}   FAILED: {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
