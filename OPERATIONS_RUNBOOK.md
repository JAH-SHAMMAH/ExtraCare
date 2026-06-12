# Fairview School Portal — Operations Runbook

**Version 1.0.** Day-to-day operations, monitoring, and incident response for
the people running the portal in production.

---

## 1. Service map
| Service | Container | Port | Notes |
|---|---|---|---|
| Frontend | `fairview-web` | 3000 | Next.js standalone |
| Backend API | `fairview-api` | 8000 | FastAPI; runs migrations on boot |
| Database | `fairview-db` | 3306 | MySQL 8 / TiDB; persistent volume `db_data` |
| Cache | `fairview-redis` | 6379 | optional |
| Reverse proxy | `fairview-nginx` | 80/443 | TLS termination |

Health: `GET /health` → `{"status":"ok","environment":"production"}`.
Admin metrics: `GET /api/v1/admin/metrics` (access-denial counters; in-process).

## 2. Routine commands
```bash
# status / logs
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f nginx

# restart a service
docker compose -f docker-compose.prod.yml restart api

# DB shell
docker compose -f docker-compose.prod.yml exec db mysql -ufairview -p fairview

# migration status / apply
docker compose -f docker-compose.prod.yml exec api alembic current
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

## 3. Backups & restore
- **Schedule:** nightly `scripts/backup_db.py` (see `BACKUP.md` for cron + off-box copy).
- **On-demand (before any deploy/migration):**
  `docker compose -f docker-compose.prod.yml exec api python scripts/backup_db.py`
- **Restore:** follow `BACKUP.md` → Restore (per-engine). After restore, run
  `alembic current` and smoke-test `/health` + a login.
- **Drill:** quarterly restore into a throwaway DB; record RTO/RPO.

## 4. Monitoring (current state + recommended)
**Available now:**
- `/health` (liveness), container healthchecks, structured JSON logs
  (`LOG_FORMAT=json`), `slow_request` log lines (>100ms), `download_audit`,
  per-tenant access-denial counters via `/admin/metrics`.

**Recommended before/just after launch (post-launch backlog):**
- External uptime monitor on `https://<domain>/health` with alerting.
- Ship container logs to a central store (retention ≥ 90 days).
- Error tracking (e.g. Sentry) on the API and web.
- DB metrics + disk-space alerting; backup-success alert (page if a nightly backup is missing/0-byte).

## 5. Logging
- API emits one structured line per request; slow paths (>100ms) are flagged.
- Audit log (`/api/v1/analytics/activity-feed`, Audit page) is immutable — use it
  for security/compliance review (logins, attendance events, record changes).
- `LOG_LEVEL` (default INFO) and `LOG_FORMAT` (`json` in prod) are env-tunable.

## 6. Common operational tasks
**Create a staff/parent/student account** (no public signup):
- Admin → Users → invite/create, assign role (`org_admin`, `manager`, `teacher`,
  `staff`, `parent`, `student`). Communicate the password securely (no email sender).

**Link a parent to a child:** ensure a `ParentGuardian` link exists (via the
student record) — required for attendance visibility and notifications.

**Rotate a password / unlock an account:** Admin → Users → set status / reset.
Accounts lock after 5 failed logins (status `LOCKED`).

**Attendance ingestion (manual / future device):**
`POST /api/v1/attendance/manual` (staff) or `POST /api/v1/attendance/events/ingest`
(bulk; the future ZKTeco adapter target). Idempotent on `(source, external_ref)`.

## 7. Incident response
| Symptom | First checks | Action |
|---|---|---|
| API won't start | `logs api` — config validator error? | Fix the offending env var (SECRET_KEY/DEBUG/DATABASE_URL/AUTO_CREATE_SCHEMA/PAYSTACK) |
| API up, DB errors | `logs db`; `db` healthy? | Verify `DATABASE_URL`/credentials; restart `db`; restore if corrupt |
| Migration failed on boot | `logs api` (alembic) | `alembic downgrade -1` or restore backup; investigate; re-deploy |
| Browser can't reach API | Network tab → calls to wrong host | `NEXT_PUBLIC_API_URL` wrong → rebuild web image |
| 403 for everyone | token/role/domain | Confirm domain gate + roles; check `/admin/metrics` denial counters |
| Parents see no alerts | guardian links / class | Verify `ParentGuardian` + `student.class_id` populated |
| Payments failing | Paystack keys/webhook | Confirm live keys + webhook URL reachable + signature secret |
| TLS errors | cert validity/paths | Renew/replace certs in `./certs`; restart nginx |

**Escalation:** capture `logs api`/`logs nginx`, the failing request ID
(`X-Request-ID`), and a recent backup reference before making changes.

## 8. Rollback (summary — full steps in DEPLOYMENT.md §8)
1. Redeploy previous `api` + `web` image tags.
2. If needed: `alembic downgrade -1`.
3. Data issue: restore latest pre-deploy backup, then redeploy.
4. Verify `/health` + principal login.

## 9. Maintenance windows
- Take a backup first. Announce to staff (no public status page yet).
- Apply updates per DEPLOYMENT.md §7. Migrations apply automatically on boot.
- Verify with the ≤30-min smoke (GO_LIVE_CHECKLIST.md).
