# Fairview School Portal — Deployment Guide

**Version:** 1.0 · **Status:** Code frozen, ready for deployment preparation.

A single-school portal (one organisation, school-only). Backend: FastAPI +
async SQLAlchemy. Frontend: Next.js 15 (standalone). Production runs on
MySQL/TiDB (or PostgreSQL) behind nginx with TLS.

---

## 1. Architecture at a glance

```
Browser ──HTTPS──▶ nginx ──/────▶ web  (Next.js standalone, :3000)
                        └──/api──▶ api  (FastAPI/uvicorn, :8000) ──▶ db (MySQL/TiDB)
                                                                  └─▶ redis (optional)
```
- One domain. nginx routes `/api/*` to the API and everything else to the frontend.
- `NEXT_PUBLIC_API_URL` is the **public** site URL (baked into the web image at build time).

## 2. Prerequisites
- Docker + Docker Compose on the host (or equivalent orchestration).
- A DNS A/AAAA record for the domain → host.
- TLS certificate (`fullchain.pem` + `privkey.pem`) — Let's Encrypt/Certbot or your CA.
- Paystack **live** keys.

## 3. Environment configuration
```bash
cp .env.production.example .env       # fill every [REQUIRED SECRET]
openssl rand -hex 32                  # → SECRET_KEY
```
**Required secrets** (prod compose fails fast if missing): `SECRET_KEY`,
`DB_PASSWORD`, `DB_ROOT_PASSWORD`, `DOMAIN`, `PAYSTACK_SECRET_KEY`,
`NEXT_PUBLIC_API_URL`. School/attendance defaults are correct as shipped.

Backend prod-safety validators (in `app/config.py`) **refuse to boot** if:
`SECRET_KEY` is the default · `DEBUG=true` · `DATABASE_URL` is SQLite ·
`AUTO_CREATE_SCHEMA=true` · `PAYSTACK_SECRET_KEY` unset — when
`ENVIRONMENT=production`. This is the safety net against dev defaults.

## 4. TLS certificates
Place certs where nginx expects them and adjust `server_name` in `nginx.conf`:
```
./certs/fullchain.pem
./certs/privkey.pem
```
nginx enforces HTTPS (HTTP→HTTPS redirect), HSTS, and standard security headers.

## 5. Database
Production uses MySQL 8 / TiDB (driver `aiomysql`, in `requirements.txt`).
`docker-compose.prod.yml` bundles a `db` service; for a managed TiDB/RDS set
`DATABASE_URL=mysql+aiomysql://user:pass@host:port/fairview` and drop the `db`
service. (PostgreSQL: swap to `asyncpg` and `postgresql+asyncpg://…`.)

**Migrations run automatically on boot** — `entrypoint.sh` runs
`alembic upgrade head` whenever `ENVIRONMENT` is `production`/`staging`, before
uvicorn serves traffic. Alembic reads `DATABASE_URL` from settings.
Migration chain: `baseline → 001_payment → 002_attendance (head)`.

## 6. Initial deployment
```bash
cp .env.production.example .env        # fill secrets
# place TLS certs in ./certs ; set nginx server_name to your domain
docker compose -f docker-compose.prod.yml up -d --build     # migrations auto-apply on api boot
docker compose -f docker-compose.prod.yml exec api python scripts/seed_fairview_school.py
#   >>> ROTATE the seeded principal/teacher passwords immediately (see GO_LIVE_CHECKLIST.md §Credentials)
docker compose -f docker-compose.prod.yml ps                # all services healthy?
curl -fsS https://<domain>/health                            # {"status":"ok","environment":"production"}
```

## 7. Application update
```bash
docker compose -f docker-compose.prod.yml exec api python scripts/backup_db.py   # pre-deploy backup
git pull
docker compose -f docker-compose.prod.yml build              # web image bakes NEXT_PUBLIC_API_URL
docker compose -f docker-compose.prod.yml up -d              # entrypoint applies new migrations
docker compose -f docker-compose.prod.yml exec api alembic current   # confirm head
```
> The frontend `NEXT_PUBLIC_API_URL` is build-time — always **rebuild** the web image when the API URL changes.

## 8. Rollback
1. **App:** redeploy the previous image tags for **both** `api` and `web`.
2. **Schema (only if a migration must be undone):**
   `docker compose -f docker-compose.prod.yml exec api alembic downgrade -1`
   (migration `002` is reversible).
3. **Data corruption:** restore the most recent pre-deploy backup (see
   `BACKUP.md` → Restore), then redeploy. Prefer restore over down-migration for data issues.
4. **Verify:** `curl https://<domain>/health` → 200, log in as principal, spot-check
   student count + recent attendance.
- Target RTO < 30 min using the latest off-box backup.

## 9. Backups
See `BACKUP.md` for the full runbook. Minimum: nightly `scripts/backup_db.py`,
14/8/6 retention, off-box copy in another region, quarterly restore drill.

## 10. Environment variable reference (backend)
| Var | Prod value | Required |
|---|---|---|
| `ENVIRONMENT` | `production` | yes |
| `DEBUG` | `false` | yes |
| `SECRET_KEY` | 32-byte random | **secret** |
| `DATABASE_URL` | `mysql+aiomysql://…` | via compose/secret |
| `AUTO_CREATE_SCHEMA` | `false` | yes |
| `ENABLE_API_DOCS` | `false` | recommended |
| `ALLOWED_ORIGINS` | `https://<domain>` | yes |
| `SINGLE_SCHOOL_MODE` | `true` | yes |
| `ALLOWED_EMAIL_DOMAIN` | `fairviewschoolng.com` | yes |
| `SCHOOL_ORG_SLUG` / `SCHOOL_NAME` | `fairview-school` / `Fairview School` | yes |
| `SCHOOL_LATE_AFTER` / `SCHOOL_EARLY_DEPARTURE_BEFORE` | `08:00` / `14:00` | default |
| `PAYSTACK_SECRET_KEY` / `PAYSTACK_PUBLIC_KEY` | live keys | **secret** |
| `REDIS_URL` / `REDIS_ENABLED` | optional | no |

**Frontend (build-time):** `NEXT_PUBLIC_API_URL` (public), `NEXT_PUBLIC_SITE_URL`.

## 11. Known operational notes
- **Email is not implemented** — password resets / invites are **not** emailed.
  Provision/communicate credentials out of band until an email sender is built.
- Seed/demo accounts and dev artifacts must be purged before launch
  (GO_LIVE_CHECKLIST.md → Cleanup).
- `tzdata` must be installed (it is, via requirements) for correct attendance
  local times (Africa/Lagos).

See also: `GO_LIVE_CHECKLIST.md`, `OPERATIONS_RUNBOOK.md`, `BACKUP.md`,
`RELEASE_NOTES_v1.0.md`.
