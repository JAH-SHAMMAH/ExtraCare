#!/usr/bin/env python
"""Read-only load ramp against the deployed API. Manual tool, not part of CI.

  python scripts/load_ramp.py                    # 10 -> 25 -> 50 concurrent users
  python scripts/load_ramp.py --stages 10,25     # pick the stages
  python scripts/load_ramp.py --seconds 60       # longer per stage

Measures correctness under load rather than raw performance: every request is a
GET a real role would make, and nothing writes. It stops early if a stage
degrades (>5% errors or p95 over 15s) instead of pushing the box until it falls
over.

REQUIRES the load-test logins to exist. Create them first, remove them after:

    python scripts/bootstrap_loadtest_accounts.py --write
    python scripts/load_ramp.py
    python scripts/bootstrap_loadtest_accounts.py --remove

and set LOADTEST_PASSWORD to the password that printed, plus LOADTEST_STUDENT_ID
to the Student.id it created (both are shown by --write).

Two constraints shape the design and are worth keeping in mind when reading
results:

  * login is capped at 20/60s PER IP and all of this traffic is one IP, so each
    role authenticates ONCE and the token is reused. Ramping login itself would
    measure the rate limiter, not the app.
  * the API round trip from a developer machine to the Render region is roughly
    0.7s before the app does anything — /health, which touches no database and
    no auth, measures about that. Subtract that floor before calling an endpoint
    slow. A first call to a given endpoint is also slower than steady state
    (statement compilation), so warm up before timing.

Database connections are sampled straight from Postgres during each stage, so
the pool ceiling is observed rather than assumed.

Baseline recorded 2026-09-03 (free tier, 4 workers, pool 5+10):
    10 VUs: 4.2 req/s, 0.0% errors, p95 3.58s, db conns max 10
    25 VUs: 2.1 req/s, 0.6% errors, p95 17.3s, db conns max 15  -> degraded
Throughput FELL as users rose, which is saturation; connections never came near
the 60 ceiling, so the limit was CPU, not the pool.
"""
import asyncio, pathlib, re, statistics, sys, time
from collections import Counter

sys.path.insert(0, r"c:\Users\SHAMMAH\OneDrive\Desktop\ExtraCare ERP\backend")

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import os

BASE = os.environ.get("LOADTEST_BASE", "https://fairview-portal.onrender.com") + "/api/v1"
PW = os.environ.get("LOADTEST_PASSWORD", "")
SID = os.environ.get("LOADTEST_STUDENT_ID", "")
if not PW or not SID:
    raise SystemExit(
        "Set LOADTEST_PASSWORD and LOADTEST_STUDENT_ID (both printed by "
        "scripts/bootstrap_loadtest_accounts.py --write)."
    )

_C = pathlib.Path(r"c:\Users\SHAMMAH\OneDrive\Desktop\ExtraCare ERP\backend\scripts\backfill_cbt_assessments.py").read_text()
DB_URL = re.search(r'^DB_URL = "(.+)"', _C, re.M).group(1)

# (role, label, path) — all reads, all 200 when unloaded.
FLOWS = [
    ("teacher", "cbt/exams",          "/cbt/exams"),
    ("teacher", "school/students",    "/school/students?page_size=25"),
    ("teacher", "school/classes",     "/school/classes"),
    ("student", "cbt/exams?for_me",   "/cbt/exams?for_me=true"),
    ("student", "report-card",        f"/school/students/{SID}/report-card?term=Term%201"),
    ("parent",  "report-card",        f"/school/students/{SID}/report-card?term=Term%201"),
]
def _arg(flag, default):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


STAGES = [int(x) for x in _arg("--stages", "10,25,50").split(",")]
STAGE_SECONDS = int(_arg("--seconds", "30"))


async def login_all(client):
    tokens = {}
    for role in ("teacher", "student", "parent"):
        r = await client.post(f"{BASE}/auth/login", json={
            "email": f"loadtest.{role}@fairviewschoolng.com", "password": PW})
        r.raise_for_status()
        tokens[role] = r.json()["access_token"]
    return tokens


async def sample_connections(engine, stop, out):
    """Poll live connection counts while a stage runs."""
    while not stop.is_set():
        try:
            async with engine.connect() as c:
                n = (await c.execute(text(
                    "SELECT COUNT(*) FROM pg_stat_activity WHERE datname='fairview_data'"
                ))).scalar()
                active = (await c.execute(text(
                    "SELECT COUNT(*) FROM pg_stat_activity "
                    "WHERE datname='fairview_data' AND state='active'"
                ))).scalar()
                out.append((n, active))
        except Exception:
            pass
        await asyncio.sleep(2.5)


async def worker(client, tokens, vu, deadline, results):
    i = vu
    while time.monotonic() < deadline:
        role, label, path = FLOWS[i % len(FLOWS)]
        i += 1
        t0 = time.monotonic()
        try:
            r = await client.get(BASE + path,
                                 headers={"Authorization": f"Bearer {tokens[role]}"})
            dt = time.monotonic() - t0
            results.append((label, r.status_code, dt))
        except Exception as e:  # noqa: BLE001
            results.append((label, type(e).__name__, time.monotonic() - t0))


def pct(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p / 100))]


async def run_stage(client, tokens, engine, vus):
    print(f"\n{'=' * 78}\nSTAGE: {vus} concurrent users for {STAGE_SECONDS}s\n{'=' * 78}")
    results, conns, stop = [], [], asyncio.Event()
    sampler = asyncio.create_task(sample_connections(engine, stop, conns))
    deadline = time.monotonic() + STAGE_SECONDS
    t0 = time.monotonic()
    await asyncio.gather(*[worker(client, tokens, v, deadline, results) for v in range(vus)])
    elapsed = time.monotonic() - t0
    stop.set()
    await sampler

    codes = Counter(str(c) for _, c, _ in results)
    lat = [d for _, c, d in results if c == 200]
    errors = sum(n for c, n in codes.items() if c != "200")
    err_rate = errors / max(1, len(results)) * 100

    print(f"  requests      : {len(results)}   ({len(results)/elapsed:.1f}/s over {elapsed:.0f}s)")
    print(f"  status codes  : {dict(codes)}")
    print(f"  error rate    : {err_rate:.1f}%")
    if lat:
        print(f"  latency (ok)  : p50 {pct(lat,50):.2f}s  p95 {pct(lat,95):.2f}s  "
              f"p99 {pct(lat,99):.2f}s  max {max(lat):.2f}s")
    if conns:
        tot = [c[0] for c in conns]
        act = [c[1] for c in conns]
        print(f"  db conns      : total max {max(tot)} (avg {statistics.mean(tot):.1f}), "
              f"active max {max(act)}   [pool ceiling 60, server usable 97]")
    print("  per endpoint:")
    by = {}
    for label, code, d in results:
        by.setdefault(label, []).append((code, d))
    for label, rows in sorted(by.items()):
        oks = [d for c, d in rows if c == 200]
        bad = Counter(str(c) for c, _ in rows if c != 200)
        print(f"    {label:<22} n={len(rows):<5} p95={pct(oks,95):.2f}s "
              f"max={max(oks) if oks else 0:.2f}s {dict(bad) if bad else ''}")

    degraded = err_rate > 5 or pct(lat, 95) > 15
    return degraded, err_rate, pct(lat, 95), (max(c[0] for c in conns) if conns else None)


async def main():
    engine = create_async_engine(DB_URL.split("?")[0], connect_args={"ssl": "require"},
                                 pool_pre_ping=True)
    summary = []
    async with httpx.AsyncClient(timeout=60.0, limits=httpx.Limits(
            max_connections=200, max_keepalive_connections=100)) as client:
        print("authenticating (3 logins — the endpoint is capped at 20/60s per IP) ...")
        tokens = await login_all(client)
        print("  ok\n")
        for vus in STAGES:
            degraded, err, p95, conns = await run_stage(client, tokens, engine, vus)
            summary.append((vus, err, p95, conns))
            if degraded:
                print(f"\n  *** STOPPING RAMP: stage degraded "
                      f"(errors {err:.1f}%, p95 {p95:.1f}s) ***")
                break
    await engine.dispose()

    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    print(f"  {'VUs':<6}{'err %':<10}{'p95 (s)':<12}{'db conns max':<14}")
    for vus, err, p95, conns in summary:
        print(f"  {vus:<6}{err:<10.1f}{p95:<12.2f}{str(conns):<14}")


asyncio.run(main())
