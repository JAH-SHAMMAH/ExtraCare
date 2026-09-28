# Fairview School Portal — Deployment Guide

**Version:** 1.0

A single-school portal (one organisation, school-only). Backend: FastAPI +
async SQLAlchemy. Frontend: Next.js 15 (standalone).

---

## 0. HOW FAIRVIEW ACTUALLY DEPLOYS — read this first

Fairview runs on **Render**, on **PostgreSQL**, as **two services**:

| | |
|---|---|
| backend | `Fairview_Portal` — API at `https://fairview-portal.onrender.com` |
| frontend | a separate Node/Next service — `https://fairview-portal-nebp.onrender.com` |
| database | Render PostgreSQL (`fairview_ndata`), driver `asyncpg` |

### MIGRATIONS APPLY THEMSELVES ON PUSH — via the Start Command

`alembic upgrade head` is folded into the backend service's **Start Command**, so
pushing to `main` migrates the database as part of bringing the new version up.
Revisions **128, 129, 130, 131 and 132 all applied this way**, unattended, in
roughly 40–60 seconds from push. §7 has the exact command.

This is worth stating plainly because this document used to say the opposite, in
bold, at the top: that migrations never applied themselves and that no migration
had ever reached this database via a Render deploy. That was true when written —
126 and 127 were applied by hand — and it stopped being true once the Start
Command was changed. It is left here rather than deleted because a runbook that
quietly reverses itself teaches nobody anything.

**What still bites, and does not go away because it now works:**

- **It runs on every START, not only on every deploy.** A free instance spins
  down when idle, so every wake runs it too. At head that is a clean no-op, so it
  costs a second or two of an already slow cold start.
- **It fails CLOSED.** `&&` means a failing migration stops uvicorn from ever
  starting. That is deliberate — an outage beats an app serving against a schema
  it disagrees with — but a bad migration takes the service down until it is
  fixed. Render a migration with `alembic upgrade <rev> --sql` first.
- **A second INSTANCE would break it.** Two instances starting together run
  Alembic concurrently and Alembic takes no lock. This is safe only while the
  service runs exactly one instance. Scaling up means moving the migration out of
  the Start Command first. (Multiple uvicorn *workers* are fine — the command
  runs once, then execs uvicorn, which forks afterwards.)
- **`Pre-Deploy Command` is still the better home** and still needs a **paid**
  instance type, which is why it is not used.

`backend/entrypoint.sh` also runs `alembic upgrade head`, and **Render still
never executes it**: the service is not built from `backend/Dockerfile`, so that
`ENTRYPOINT` is never invoked. It is dead code on Render. Do not "fix" a
migration problem by editing it — nothing runs it.

**To apply one by hand** (the escape hatch, and how 126/127 were applied):

```bash
cd backend
# ALWAYS look first: know exactly which revisions will run.
DATABASE_URL="postgresql+asyncpg://<prod-dsn>" python -m alembic current
DATABASE_URL="postgresql+asyncpg://<prod-dsn>" python -m alembic history -r current:head
DATABASE_URL="postgresql+asyncpg://<prod-dsn>" python -m alembic upgrade head
```

Verify either way by READING `alembic_version`, never by probing the API. A
healthy API response proves nothing: the old instance serves happily while
nothing new has shipped, and on a free instance it may not even have restarted
yet. The only thing that answers "did the migration run" is the row itself.

```sql
SELECT version_num FROM alembic_version;
SELECT to_regclass('public.<new_table>') IS NOT NULL;
```

### The docker-compose material below is NOT how Fairview runs

Sections 1-6 describe a self-hosted nginx + MySQL + docker-compose stack. It is
kept for local development (`docker-compose.yml`) and as a self-hosting
reference. **It does not describe production.** Do not diagnose a production
problem from it.

---

## 1. Architecture at a glance — self-hosted topology (see §0 for Render)

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

**Migrations on Render: NOT automatic — see §0.** `entrypoint.sh` would run
`alembic upgrade head` when `ENVIRONMENT` is `production`/`staging`, and that
happens only under Docker (`docker-compose`, below). Render does not run it.
Alembic reads `DATABASE_URL` from settings.

The migration chain is long and grows every release — read the current head from
the code rather than from this file, which will always be out of date:

```bash
cd backend && python -m alembic heads
```

## 5b. Persistent storage for uploaded media (REQUIRED)
Uploaded images, **documents**, and profile photos must land on durable storage —
otherwise they're **wiped on every redeploy / restart** on an ephemeral filesystem
(Render's default, and any plain container). There are two supported backends;
**pick one:**

### Option A — Cloudinary (RECOMMENDED; no disk, survives everything)
Set one env var on the backend service:

```
CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>
```

Get it free from the Cloudinary dashboard (Account Details → "API environment
variable"). When set, all uploads (feed images/documents, avatars, messenger
media) go to Cloudinary's CDN and the stored URL is an absolute
`https://res.cloudinary.com/…`. Survives redeploys **and** works across multiple
app instances — nothing else to configure, and the ephemeral-storage warning goes
away. The `cloudinary` package is already in `requirements.txt`.

### Option B — local disk on a Render Persistent Disk
If you'd rather not use Cloudinary, uploads fall back to `UPLOAD_DIR` (served at
`/uploads/<org_id>/…`). That path **must** be a mounted persistent disk, or files
vanish on redeploy. The API logs a loud `WARNING` at boot if `UPLOAD_DIR` looks
ephemeral in `production`/`staging` **and** `CLOUDINARY_URL` is not set.

- **Render:** attach a **Persistent Disk** to the backend (`api`) service —
  e.g. Name `uploads`, **Mount Path** `/var/uploads`, Size `1–5 GB` — then set
  env **`UPLOAD_DIR=/var/uploads`** and redeploy. Files now survive deploys.
  > A Render disk binds to a **single instance**. If you scale `api` beyond one
  > instance, switch to object storage (S3 / Cloudinary) instead — a disk can't
  > be shared. (No code change needed there beyond a storage adapter.)
- **Docker Compose:** mount a named volume at the container's `UPLOAD_DIR`
  (e.g. `uploads:/app/uploads` with `UPLOAD_DIR=/app/uploads`) so it persists
  across `up -d --build`.
- **Already-lost files** (wiped by earlier ephemeral redeploys) cannot be
  recovered — re-upload them once the disk is attached.

## 6. Initial deployment — SELF-HOSTED DOCKER ONLY (not Fairview; see §0)
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

### On Render (how Fairview updates)

1. Push to `main`. Render auto-deploys the service(s) connected to that branch
   (confirmed working).
2. A migration is applied by the **Start Command** — see below. Nothing else runs
   it.
3. Confirm by reading the database (§0), not by probing the API.

#### Migrations via the Start Command (current setup — free instance)

`Pre-Deploy Command` is the natural home for this, but it **requires a paid
instance type** and is unavailable on ours. So the migration is folded into the
Start Command instead (dashboard → backend service → **Settings** →
**Start Command**):

```
python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Adapt, don't paste: keep whatever uvicorn flags the service already has, and
prefix `cd backend && ` if the service's **Root Directory** is the repo root
rather than `backend` (that is where `alembic.ini` lives). `python -m alembic`
rather than bare `alembic` pins it to the same interpreter as the app.

No DSN is needed — `alembic/env.py` reads `settings.DATABASE_URL`, so it inherits
the service's own environment.

**What to understand about this approach:**

- **It runs on every START, not only every deploy.** A free instance spins down
  when idle, so each wake runs it too. At head that is a verified clean no-op
  (exit 0, no DDL), so it is safe — it just adds a second or two to an already
  slow cold start.
- **It fails CLOSED.** `&&` means a migration error stops uvicorn ever starting:
  an outage, rather than an app serving against a schema it disagrees with. That
  is usually the right trade for a school portal, but know that a bad migration
  takes the service down until it is fixed, and recovery on a free instance means
  another deploy. Test migrations locally first — `alembic upgrade <rev> --sql`
  renders the DDL without touching anything.
- **Workers are NOT a problem.** The command runs once, then execs uvicorn, which
  forks its workers afterwards — so `--workers N` does not produce N concurrent
  Alembic runs.
- **A second INSTANCE would be a problem.** Two instances starting together would
  run Alembic concurrently, and Alembic takes no lock to make that safe. Revisit
  this the moment the service scales past one instance, or moves to a paid plan
  where `Pre-Deploy Command` becomes available — that is strictly better, because
  it runs once per deploy rather than once per boot.

#### Alternative: the Build Command

`pip install -r requirements.txt && python -m alembic upgrade head` also works and
runs once per deploy rather than per boot. The trade-off is that a build can
succeed while the deploy then fails, leaving the schema ahead of the running
code. Harmless for additive migrations (new tables/columns the old code ignores);
not harmless for one that drops or rewrites anything. Start Command is preferred
here for that reason.

Render `Jobs`/`Cron Jobs` are paid features and are not an option on this plan.

A **pre-deploy backup** is still worth taking: `python scripts/backup_db.py`
with `DATABASE_URL` pointed at production (see `BACKUP.md`).

### Self-hosted docker-compose (not Fairview)
```bash
docker compose -f docker-compose.prod.yml exec api python scripts/backup_db.py   # pre-deploy backup
git pull
docker compose -f docker-compose.prod.yml build              # web image bakes NEXT_PUBLIC_API_URL
docker compose -f docker-compose.prod.yml up -d              # entrypoint DOES apply migrations here
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
| `DB_POOL_SIZE` | `5` — **per worker** (see note below) | default |
| `DB_MAX_OVERFLOW` | `10` — **per worker** (see note below) | default |
| `AUTO_CREATE_SCHEMA` | `false` | yes |
| `CLOUDINARY_URL` | `cloudinary://<key>:<secret>@<cloud>` | **recommended — §5b Option A** |
| `UPLOAD_DIR` | durable path, e.g. `/var/uploads` (only if not using Cloudinary) | §5b Option B |
| `ENABLE_API_DOCS` | `false` | recommended |
| `ALLOWED_ORIGINS` | `https://<domain>` | yes |
| `SINGLE_SCHOOL_MODE` | `true` | yes |
| `ALLOWED_EMAIL_DOMAIN` | `fairviewschoolng.com` | yes |
| `SCHOOL_ORG_SLUG` / `SCHOOL_NAME` | `fairview-school` / `Fairview School` | yes |
| `SCHOOL_LATE_AFTER` / `SCHOOL_EARLY_DEPARTURE_BEFORE` | `08:00` / `14:00` | default |
| `PAYSTACK_SECRET_KEY` / `PAYSTACK_PUBLIC_KEY` | live keys | **secret** |
| `REDIS_URL` / `REDIS_ENABLED` | optional | no |

**Frontend (build-time):** `NEXT_PUBLIC_API_URL` (public), `NEXT_PUBLIC_SITE_URL`.

### Connection-pool sizing (read before raising either value)
`DB_POOL_SIZE` and `DB_MAX_OVERFLOW` are **per uvicorn worker**, and each worker
is a separate process with its own pool. What the database sees is:

```
(DB_POOL_SIZE + DB_MAX_OVERFLOW) x worker count   <=   max_connections - superuser_reserved_connections
        (5 + 10 = 15)            x 4 (Dockerfile) =  60   <=   100 - 3 = 97      ✅ 37 spare
```

Check the ceiling on the server itself rather than assuming the plan's
documentation — `SHOW max_connections;` and `SHOW superuser_reserved_connections;`.
The current Render Postgres reports 100 and 3.

The spare is not slack. An Alembic run (whether by hand, by a Pre-Deploy
Command, or by `entrypoint.sh` under Docker) opens its own connection, and
psql/monitoring/backup jobs each need a slot. The previous defaults (10/20) came
to 120 — more than the database allows — so under load the app could exhaust its
own database. If you raise either value, or the worker count in the Dockerfile
`CMD`, redo the arithmetic above first.

## 11. Known operational notes
- **Email is not implemented** — password resets / invites are **not** emailed.
  Provision/communicate credentials out of band until an email sender is built.
- Seed/demo accounts and dev artifacts must be purged before launch
  (GO_LIVE_CHECKLIST.md → Cleanup).
- `tzdata` must be installed (it is, via requirements) for correct attendance
  local times (Africa/Lagos).

See also: `GO_LIVE_CHECKLIST.md`, `OPERATIONS_RUNBOOK.md`, `BACKUP.md`,
`RELEASE_NOTES_v1.0.md`.
