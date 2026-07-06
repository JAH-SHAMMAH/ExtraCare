# Fairview School Portal — Launch Checklist

Single-school production deployment. Backend + web are **release-ready**
(310 backend tests passing, frontend build clean). This checklist is the
authoritative go-live runbook; tick every box before accepting live traffic.

---

## 0. Pre-flight (one-time)
- [ ] Provision the production DB (MySQL/TiDB recommended; **not** SQLite —
      the config validator refuses to boot on SQLite in production).
- [ ] Provision Redis only if you intend to scale to >1 app instance (the rate
      limiter is in-memory per-process today; single instance needs no Redis).
- [ ] DNS + TLS for the portal host (e.g. `portal.fairviewschoolng.com`).
- [ ] Generate `SECRET_KEY`: `openssl rand -hex 32`.
- [ ] Obtain `PAYSTACK_SECRET_KEY` (prod boot fails without it).

## 1. Environment configuration  (see `.env.example`)
- [ ] `ENVIRONMENT=production`  → enforces SECRET_KEY/DEBUG/SQLite/Paystack checks.
- [ ] `DEBUG=false`, `ENABLE_API_DOCS=false`, `AUTO_CREATE_SCHEMA=false`.
- [ ] `SECRET_KEY` = the generated 32-byte hex (NOT the placeholder).
- [ ] `DATABASE_URL` = production MySQL/TiDB async DSN.
- [ ] `SINGLE_SCHOOL_MODE=true`, `SCHOOL_ORG_SLUG`, `ALLOWED_EMAIL_DOMAIN` set.
- [ ] **CORS:** `ALLOWED_ORIGINS=https://portal.fairviewschoolng.com` — EXACT
      origin(s), never `*` (requests are credentialed under cookie auth).
- [ ] `PAYSTACK_SECRET_KEY` set; `PAYSTACK_CALLBACK_URL` points at the prod host.
- [ ] **Rate limiting:** `RATE_LIMITS_ENABLED=true`. For the first hours set
      `RATE_LIMIT_MONITOR_ONLY=true` to observe, then flip to `false`.
- [ ] Frontend `NEXT_PUBLIC_API_URL=https://api.fairviewschoolng.com` (the API host).

### Cookie auth rollout (do this as a *coordinated* step, not at first boot)
Cookie auth ships **off** (Bearer-token mode = today's behaviour). Turn it on
only when you flip BOTH flags together:
- [ ] Backend `COOKIE_AUTH_ENABLED=true`
- [ ] Backend `COOKIE_SECURE=true`  (**required** over https; false only on local http)
- [ ] Backend `COOKIE_SAMESITE=lax` (or `strict`), `COOKIE_DOMAIN=` (host-only)
- [ ] Frontend `NEXT_PUBLIC_COOKIE_AUTH=true` (rebuild the web app)
- [ ] Verify login sets `access_token`/`refresh_token` (HttpOnly) + `csrf_token`,
      that `/auth/me` works without a Bearer header, WebSockets connect, and a
      mutating request without `X-CSRF-Token` is rejected (403).
> Mismatched flags break auth. If anything misbehaves, set both flags back to
> `false` (no redeploy of code needed) — instant revert to Bearer mode.

## 2. Database migrations
- [ ] Status: **Phase 8 introduced no schema changes.** Current head is
      `002_add_attendance_events` (chain: baseline → 001_payment_infra →
      002_attendance_events).
- [ ] On deploy, `entrypoint.sh` runs `alembic upgrade head` automatically when
      `ENVIRONMENT` is production/staging. Confirm the log line
      `[entrypoint] migrations complete.`
- [ ] Manual equivalent (if not using the container entrypoint):
      `cd backend && alembic upgrade head`
- [ ] Verify: `alembic current` == head.

## 3. Admin bootstrap
- [ ] Seed the school org + Principal:
      `cd backend && python scripts/seed_fairview_school.py`
      → creates org `fairview-school` + admin `principal@fairviewschoolng.com`.
- [ ] **Immediately change the seeded Principal password** (seed default is for
      bootstrap only) and store it in the org password manager.
- [ ] Confirm the Principal can log in and reach the dashboard.
- [ ] Provision real staff/teacher/parent/student accounts (Users admin) — the
      domain gate requires `@fairviewschoolng.com` and an existing active account
      (no public self-signup in single-school mode).

## 4. Build & deploy
- [ ] Backend image builds (`Dockerfile`); container runs `entrypoint.sh` → uvicorn.
- [ ] Frontend: `cd frontend && npm ci && npm run build` (Next standalone output).
- [ ] Deploy behind TLS; ensure the reverse proxy forwards `X-Forwarded-For`
      (used by rate limiting + audit IP capture).
- [ ] Health: `GET /api/health` (or root) returns 200 after migrations.

## 5. Smoke tests (against the deployed environment)
- [ ] `EMAIL=principal@fairviewschoolng.com PASSWORD=… BASE_URL=https://api…
      sh backend/scripts/deploy_smoke.sh` — all checks PASS.
- [ ] Manual: login → dashboard loads; Messenger connects (WS); create/read a
      student; mark attendance; view audit log (Admin only); a teacher cannot
      see admin-only pages or hit admin APIs (403).
- [ ] Confirm a rate-limit 429 fires on the login bucket (>20 rapid logins).

## 6. Backup / restore
- [ ] Schedule backups: `python backend/scripts/backup_db.py` (uses `MYSQL_PWD`
      via env; password never on argv). Store off-host (e.g. object storage).
- [ ] Verify a backup restores into a scratch DB and the app boots against it.
- [ ] Document RPO/RTO with the school (recommend nightly + pre-deploy snapshot).

## 7. Monitoring / logging
- [ ] Ship structured logs (JSON in prod) to your aggregator. Key signals:
      `slow_request` (>100ms), `rate_limit_exceeded` (logger `extracare.security`,
      includes user/org/ip/bucket/threshold), `module_access_denied`,
      `role_permission_denied`.
- [ ] `/admin/metrics` exposes denial counters (rate-limit + permission denials)
      — wire a periodic scrape/alert on abnormal spikes.
- [ ] Audit trail: the Admin **Audit Log** page surfaces every academic +
      financial mutation (create/update/delete, grade, payment, SMS send).
- [ ] External uptime monitor on the health endpoint + a synthetic login.
- [ ] Alert on 5xx rate and on app restarts (in-memory rate-limit + WS state
      reset on restart — expected, but a restart storm is worth knowing about).

## 8. Rollback procedure
- [ ] **Cookie auth issue:** set `COOKIE_AUTH_ENABLED=false` (backend) +
      `NEXT_PUBLIC_COOKIE_AUTH=false` (frontend rebuild) → instant revert to
      Bearer mode. No code change.
- [ ] **Rate-limit over-blocking:** set `RATE_LIMIT_MONITOR_ONLY=true` (stops all
      429s, keeps logging) or `RATE_LIMITS_ENABLED=false`; tune
      `RATE_LIMIT_OVERRIDES` per bucket.
- [ ] **Bad release:** redeploy the previous container image/tag.
- [ ] **Schema regression:** `alembic downgrade <previous_revision>` (Phase 8
      added none, so this only applies to pre-Phase-8 migrations).
- [ ] **Data loss:** restore the latest verified backup (§6), then replay since
      the snapshot if applicable.

---

### Sign-off
- [ ] Engineering: build green, tests green, smoke PASS.
- [ ] School admin: Principal access confirmed, accounts provisioned.
- [ ] Ops: backups scheduled + restore tested, monitoring live, rollback rehearsed.
