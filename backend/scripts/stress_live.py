"""
Live-session stress harness.

Spins up N async WebSocket viewers against /live/ws/{session_id}?token=...
to measure how the signaling layer holds up under classroom-scale load
(50–100 concurrent joins). Does NOT exercise WebRTC media — WebRTC is
peer-to-peer and cannot be load-tested from a single Python process anyway.
What we measure here is the signaling server, which is the only shared
bottleneck before fan-out reaches the host browser.

Metrics reported:
  - connect success rate
  - p50 / p95 / p99 connect latency (ms)
  - p50 / p95 viewer_joined broadcast latency (ms)
  - error / disconnect counts

Usage:
    BASE_URL=http://localhost:8000 \
    SESSION_ID=<uuid> \
    TOKENS_FILE=./tokens.txt \
    NUM_VIEWERS=75 \
    python scripts/stress_live.py

tokens.txt is one JWT per line (at least NUM_VIEWERS lines). Generate via
a dev helper or by logging in N seeded student accounts.

If TOKENS_FILE is absent but TOKEN is set, that single token is reused for
every viewer — the backend's per-user join limits may reject duplicates,
so prefer distinct accounts when you can.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import websockets
except ImportError:
    print("stress_live.py requires the 'websockets' package: pip install websockets")
    sys.exit(2)


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
SESSION_ID = os.environ.get("SESSION_ID", "").strip()
TOKENS_FILE = os.environ.get("TOKENS_FILE", "").strip()
SINGLE_TOKEN = os.environ.get("TOKEN", "").strip()
NUM_VIEWERS = int(os.environ.get("NUM_VIEWERS", "50"))
RAMPUP_SECONDS = float(os.environ.get("RAMPUP_SECONDS", "5"))
HOLD_SECONDS = float(os.environ.get("HOLD_SECONDS", "10"))


def _ws_url(token: str) -> str:
    scheme = "wss" if BASE_URL.startswith("https") else "ws"
    host = BASE_URL.split("://", 1)[1]
    return f"{scheme}://{host}/live/ws/{SESSION_ID}?token={token}"


@dataclass
class ViewerResult:
    index: int
    connected: bool = False
    connect_ms: Optional[float] = None
    first_event_ms: Optional[float] = None
    error: Optional[str] = None
    messages_received: int = 0


async def run_viewer(idx: int, token: str, stop: asyncio.Event) -> ViewerResult:
    result = ViewerResult(index=idx)
    url = _ws_url(token)
    started = time.perf_counter()
    try:
        async with websockets.connect(url, open_timeout=15, close_timeout=5) as ws:
            result.connect_ms = (time.perf_counter() - started) * 1000
            result.connected = True
            # Wait for the first "connected" / "viewer_joined" / "error" event.
            event_started = time.perf_counter()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                result.first_event_ms = (time.perf_counter() - event_started) * 1000
                result.messages_received += 1
                try:
                    data = json.loads(raw)
                    if data.get("event") == "error":
                        result.error = data.get("detail", "server_error")
                except (ValueError, TypeError):
                    pass
            except asyncio.TimeoutError:
                result.error = "no_first_event"
            # Hold connection open; drain any further messages until stop signal.
            while not stop.is_set():
                try:
                    await asyncio.wait_for(ws.recv(), timeout=0.5)
                    result.messages_received += 1
                except asyncio.TimeoutError:
                    continue
                except websockets.ConnectionClosed:
                    result.error = result.error or "closed_by_server"
                    break
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"[:120]
    return result


def _pct(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    idx = max(0, min(len(values) - 1, int(round(pct / 100 * (len(values) - 1)))))
    return sorted(values)[idx]


def _load_tokens() -> list[str]:
    if TOKENS_FILE:
        with open(TOKENS_FILE, encoding="utf-8") as f:
            tokens = [line.strip() for line in f if line.strip()]
        if len(tokens) < NUM_VIEWERS:
            # Cycle if file is shorter than target.
            tokens = (tokens * ((NUM_VIEWERS // max(1, len(tokens))) + 1))[:NUM_VIEWERS]
        return tokens[:NUM_VIEWERS]
    if SINGLE_TOKEN:
        return [SINGLE_TOKEN] * NUM_VIEWERS
    print("Set TOKENS_FILE=<path> or TOKEN=<jwt>.")
    sys.exit(2)


async def main() -> int:
    if not SESSION_ID:
        print("SESSION_ID env var is required.")
        return 2

    tokens = _load_tokens()
    stop = asyncio.Event()
    tasks: list[asyncio.Task[ViewerResult]] = []

    print(
        f"Ramping up {NUM_VIEWERS} viewers over {RAMPUP_SECONDS}s "
        f"against {BASE_URL} session={SESSION_ID}"
    )
    delay_between = RAMPUP_SECONDS / max(1, NUM_VIEWERS)
    for i, tok in enumerate(tokens):
        tasks.append(asyncio.create_task(run_viewer(i, tok, stop)))
        await asyncio.sleep(delay_between)

    print(f"All viewers scheduled — holding for {HOLD_SECONDS}s…")
    await asyncio.sleep(HOLD_SECONDS)
    stop.set()
    results = await asyncio.gather(*tasks, return_exceptions=False)

    connected = [r for r in results if r.connected]
    failed = [r for r in results if not r.connected]
    with_error = [r for r in results if r.error]
    connect_times = [r.connect_ms for r in connected if r.connect_ms is not None]
    first_event_times = [r.first_event_ms for r in connected if r.first_event_ms is not None]

    print("\n── Stress report ──")
    print(f"  viewers requested:     {NUM_VIEWERS}")
    print(f"  connected:             {len(connected)}  ({len(connected) / NUM_VIEWERS:.1%})")
    print(f"  failed to connect:     {len(failed)}")
    print(f"  had error at any point:{len(with_error)}")
    if connect_times:
        print(
            f"  connect_ms  p50={_pct(connect_times, 50):.0f} "
            f"p95={_pct(connect_times, 95):.0f} "
            f"p99={_pct(connect_times, 99):.0f} "
            f"max={max(connect_times):.0f}"
        )
    if first_event_times:
        print(
            f"  first_event_ms p50={_pct(first_event_times, 50):.0f} "
            f"p95={_pct(first_event_times, 95):.0f} "
            f"max={max(first_event_times):.0f}"
        )
    if failed:
        counts: dict[str, int] = {}
        for r in failed:
            key = (r.error or "unknown").split(":", 1)[0]
            counts[key] = counts.get(key, 0) + 1
        print("  failure breakdown:")
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"    {v:4d}  {k}")

    # Return non-zero if success rate dropped below 95% — useful as a CI gate.
    return 0 if len(connected) / NUM_VIEWERS >= 0.95 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
