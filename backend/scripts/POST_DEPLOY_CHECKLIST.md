# Post-deploy verification — first 30 minutes

High-signal checks only. If anything in **Stop-ship** trips, roll back.

## T+0 — immediately after promote

- [ ] `GET /health` → 200, `environment=production`, expected version.
- [ ] Run `scripts/deploy_smoke.sh` against prod URL with a prod admin account. All checks PASS.
- [ ] Log shipper is receiving lines from the new deploy (timestamps advancing).
- [ ] Log lines are valid JSON; `org_id` / `user_id` / `event` are top-level keys, not nested in a message blob.

## T+5 — critical flow spot-check (UI)

- [ ] Admin: dashboard loads, tuckshop + behaviour widgets render numbers (not spinners, not zeros-where-data-exists).
- [ ] Student: `/classroom/assignments?for_me=true` returns only their items; switching off `for_me` is forbidden or empty per role.
- [ ] One CBT exam: start inside live window succeeds; outside-window attempt returns a structured 4xx.

## T+15 — signal sweep

- [ ] Error rate: unhandled-500 count over the window is **0** (or matches pre-deploy baseline).
- [ ] Auth: `event=login_failed` rate is not elevated vs. the prior hour.
- [ ] p95 latency on `/tuckshop/sales/summary` and `/behaviour/summary` ≤ 300 ms (prod DB should beat SQLite numbers comfortably).
- [ ] These events have appeared at least once in logs:
  - `event=school_context_resolved`
  - `event=cbt_attempt_rejected` (if any out-of-window attempts)
  - `event=feedback_listed`

## Stop-ship signals (roll back immediately)

- 5xx rate > 1% sustained for 2 minutes.
- Any log line containing a stack trace referencing `alembic`, `IntegrityError`, or `OperationalError`.
- `/health` flapping or returning non-200.
- Auth endpoint returning 500 (not 401/403).
- Schema mismatch errors (`no such column`, `unknown column`) — indicates migration drift.

## Rollback

1. Re-promote the prior image/tag.
2. If a migration was applied: `alembic downgrade -1` **only if** the down-revision is known-safe; otherwise restore from the pre-deploy snapshot.
3. Post the incident timestamp + failing checklist item for the postmortem.

## Livestream — module-specific checks

Run these in addition to the generic sweep whenever the Live deploy touches
signaling, recordings, or plan enforcement. The Live module has external
dependencies (TURN relays, blob storage) that don't show up in the core
health check — watch them explicitly the first hour after each ship.

### T+0

- [ ] `GET /live/ice-config` → 200, `iceServers` array is non-empty, and at least one entry includes a TURN URL (not only STUN).
- [ ] Recording upload dir (`$UPLOAD_DIR/<org>/live/`) is writable by the API process. Empty is fine — creation-on-write is the contract.
- [ ] `UPLOAD_DIR` is on persistent storage, not ephemeral container FS. A rolling deploy that wipes this wipes every recording not yet flushed to cold storage.
- [ ] Plan caps in `app/core/plans.py` match the pricing page and billing product IDs (PRO = 10 GB, ENTERPRISE = unlimited). Drift here turns into silent overcharge or under-block.

### T+5 — end-to-end smoke

- [ ] Teacher login → "Go Live" from a timetable slot → viewer joins from a second browser → speaking-ring + connection badge both render → end session. Watch for retries or reconnect overlays that shouldn't be happening on a clean network.
- [ ] Host starts recording → stops → upload succeeds (HTTP 201) → recording shows up in session history on reload. File size on disk matches `file_size` column.
- [ ] Force a connection drop on the viewer side (toggle wifi, ~5s). ReconnectOverlay appears → resolves back to "Connected" without duplicate attendance rows being created (`LiveAttendance` count stays flat, `left_at` is cleared on resume).

### T+15 — signal sweep

- [ ] Join-success rate: `event=live.ws.connected` / `event=live.ws.attempted` ≥ 95% across the window.
- [ ] Reconnect giveup rate: `event=live.reconnect.gave_up` occurrences near zero. A spike here means TURN is unhealthy or signaling is flapping.
- [ ] Recording quota 402s: `status=402, reason=recording_storage_exceeded` are legitimate (paid tenants near cap) — investigate any on FREE tenants as they shouldn't reach the upload path at all.
- [ ] `recording_storage_mb` in the usage table advances within a few seconds of a successful upload. Lag here means the usage flush isn't firing.

### Livestream stop-ship signals

- `/live/ws/{id}` WebSocket 4xx/5xx rate > 2% — signaling broken, nobody can join.
- TURN provider quota exhausted (403s or "credentials_invalid" in ICE logs). Peers on restrictive networks will silently fail; rotate creds or roll back.
- Recordings table growing but `UPLOAD_DIR` usage flat — blob path misconfig; uploads returning 201 but bytes dropped on the floor. File_size column audit: any rows where file_size > 0 but `os.path.exists(UPLOAD_DIR/file_path)` is false.

### Recordings — backup & restore

Recordings are the only Live asset that isn't reproducible — session/attendance/usage rows can be regenerated from logs, blobs cannot. Treat `UPLOAD_DIR/<org>/live/` as first-class persistent data alongside the database.

- Snapshot cadence: same schedule as the DB (at least nightly). The size-weighted growth rate of `LiveRecording.file_size` tells you whether daily is still sufficient as tenants grow.
- Restore drill: quarterly, verify you can restore **one tenant's** recordings from snapshot to a staging mount and the existing `file_path` rows in the DB resolve to valid files. A snapshot you've never restored from is not a backup.
- Retention policy: default is "keep for plan's recording_storage_mb window". Enterprise is unlimited — talk to the tenant before ever purging.

### Pilot rollout (first 1–2 schools)

While a school is on pilot, watch these every morning for the first week and weekly after that. Keep the numbers in a shared doc so the sales conversation has data, not anecdotes.

- Join success rate per school (should be ≥ 95%).
- Average reconnects per session (should trend toward < 1).
- Recording upload success rate (should be 100% — anything else is a ship-blocker).
- Qualitative: a teacher phone call at the end of week one. Any phrase like "confusing" or "I gave up" triggers a same-day UX pass before we widen the pilot.
