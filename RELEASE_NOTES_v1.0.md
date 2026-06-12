# Fairview School Portal — Release Notes v1.0

**Status:** Code frozen · Ready for deployment preparation & stakeholder review
**Type:** Major release (multi-industry ERP → dedicated single-school portal)

---

## Part A — Management Release Note (executive summary)

The **Fairview School Portal v1.0** is ready for production preparation. We have
transformed a general, multi-industry ERP platform into a secure, dedicated
portal built solely for **Fairview School** — for administrators, teachers,
parents, and students.

**What this delivers for the school**
- **One secure portal** for the whole school — no unrelated industry features,
  no confusing setup. Staff, parents, and students each see only what's relevant
  to them.
- **Restricted, secure access:** only verified **@fairviewschoolng.com** accounts
  can sign in; there is no public sign-up. Accounts are created by the school.
- **Real-time parent safety:** parents are notified the instant their child
  checks in or out — *"… has successfully checked into Fairview School at 7:32 AM."*
- **Complete school operations retained and improved:** students, attendance,
  results/CBT, timetable, fees, HR, reporting, and communications.
- **Future-ready:** the attendance system is built so the school's existing
  **ZKTeco** devices can be connected later with no rework, and the platform is
  positioned for mobile apps, push notifications, and AI tutoring.

**Quality & safety:** the migration was non-destructive and reversible. The
backend test suite passes (236 tests; 2 unrelated, pre-existing failures in a
legacy billing area not used by the school). Production builds are verified, and
the system refuses to start with unsafe development settings.

**Before launch (operational, not development):** install TLS certificates, set
production secrets, schedule automated backups, and rotate the initial seeded
passwords. These are covered in the Go-Live Checklist.

**One transparency note:** automated **email** (e.g. emailed password resets) is
**not** part of v1 — credentials are managed by administrators directly. It is on
the post-launch backlog.

---

## Part B — Release Summary (detail)

### B1. Original project scope
Convert the existing multi-industry **ERP** (Schools + Hospitals + Businesses,
multi-tenant) into a **dedicated Fairview School Portal**: one organisation, one
school, one brand. Preserve all working school functionality, restrict access to
the school's email domain, add real-time attendance with parent notifications
designed for future ZKTeco integration, and remove multi-industry/tenant
concepts from the user experience — all **without** destructive rewrites.

### B2. Major completed milestones
1. **Architecture analysis & migration plan** (non-destructive, reversible).
2. **Single-school mode** — server resolves the one organisation; no tenant
   selection, no organisation onboarding.
3. **Domain-restricted authentication** — `@fairviewschoolng.com` gate layered
   onto the existing secure login.
4. **ZKTeco-ready attendance system** — event layer, ingestion service, parent
   notifications, and dashboards.
5. **Attendance dashboards** for Parent, Teacher, and Admin + notification views.
6. **Hospital/Business removal** from the user-facing product (deprecated in
   backend, removed from the UI).
7. **Production-readiness remediation** — payments permissions, backups, signup
   replacement, branding cleanup.
8. **Deployment infrastructure** — production compose, auto-migrations, TLS
   reverse proxy, environment templates.
9. **Code freeze + full documentation set.**

### B3. Features delivered
- **Single-school portal** with role-scoped experiences (Admin, Teacher, Parent,
  Student) and school-only navigation.
- **Student management**, classes, subjects, guardians, bulk CSV import.
- **Attendance**: daily marking (existing) + new **event-sourced** check-in/out,
  daily/monthly summaries, late-arrival & absence analytics, and three role
  dashboards.
- **Instant parent notifications** on arrival/departure (in-app), guardian-scoped.
- **Academics**: gradebook, exams, **CBT**, timetable, lesson planner, report cards.
- **Fees & payments** (Paystack) with parent payment and admin reconciliation.
- **HR & leave**, **library**, **transport**, **behaviour/pastoral**, **clubs**,
  **journals**, **tuckshop**, **bulk SMS**, **messenger**, **news feed**,
  **live classes**, analytics, audit log.

### B4. Security improvements
- **Email-domain authentication gate** (`@fairviewschoolng.com`) — necessary but
  not sufficient: the account must also exist, be active, and pass all checks;
  **no auto-provisioning**.
- **Public registration disabled** (single-school mode); the signup page is a
  clear "by invitation" notice.
- **Payments RBAC corrected** — `payments` permissions granted to the roles that
  transact (admin full/reconcile, management read/write, parent read).
- **Production safety validators** reject dev defaults (default `SECRET_KEY`,
  `DEBUG=true`, SQLite, `AUTO_CREATE_SCHEMA`, missing Paystack) at boot.
- Retained: JWT (30-min access / 7-day refresh), login rate limiting, failed-login
  lockout, immutable audit log, tenant-scoped queries.
- TLS reverse proxy with HSTS and security headers; fail-fast required secrets in
  the production stack.

### B5. Attendance system implementation
- **`AttendanceEvent`** model — timestamped check-in/check-out events with
  `source` (manual / **zkteco** / import / api), `external_ref` (device id),
  `device_id`, `raw_payload`. Unique `(org, source, external_ref)` → **idempotent**.
- **`AttendanceIngestionService.ingest()`** — the single entry point (the
  **adapter port** a future ZKTeco device pushes to). It dedups, **derives the
  daily attendance record** (present/late vs the 08:00 cutoff in Africa/Lagos),
  writes an **audit** entry, and sends **parent notifications**.
- **APIs:** `daily`, `monthly`, `manual`, `events/ingest`, `student/{id}/history`.
- **Notifications:** in-app, guardian-scoped, exact required copy; payload is
  outbox-ready for future SMS/push without rework.
- **Dashboards:** Parent (per-child summary + history + alerts), Teacher (class
  roster + manual check-in/out), Admin (daily/monthly + late & absence analytics).
- **No ZKTeco hardware integration was built** (per scope) — only the clean
  extension point for it.

### B6. Fairview migration summary
- Strategy: **pin-and-deprecate, not rip-and-rewrite.** The multi-tenant core was
  retained for stability/reversibility; single-school behaviour is enforced at the
  boundary via `SINGLE_SCHOOL_MODE`.
- One canonical organisation seeded (school / enterprise / onboarding complete).
- Hospital & Business **deprecated** in the backend (code retained, routers
  unmounted) and **removed** from the user-facing frontend (pages, routes,
  marketing, menus, API clients, import presets).
- Branding changed from "ExtraCare ERP" to **"Fairview School Portal"** across the
  user-facing surface; workspace/industry terminology removed from the UI.

### B7. Deployment infrastructure summary
- **`docker-compose.prod.yml`** — production stack (MySQL 8/TiDB, Redis, nginx),
  fail-fast required secrets, migrations on boot.
- **Auto-migrations** via `backend/entrypoint.sh` (`alembic upgrade head` in
  prod/staging) before serving.
- **`nginx.conf`** — TLS, HTTP→HTTPS, HSTS, `/api` proxy, WebSocket upgrade,
  security headers.
- **Frontend standalone build** (`output: "standalone"`) for the container image;
  **`NEXT_PUBLIC_API_URL`** is a required public build arg.
- **Async prod DB driver** (`aiomysql`) added; **`tzdata`** for correct attendance
  timezones.
- **Backups:** `scripts/backup_db.py` + `BACKUP.md` runbook (schedule, retention,
  off-box, restore drill).
- Environment templates: `.env.production.example` (required-secret markers),
  updated `.env.example` (backend + frontend).

### B8. Outstanding future enhancements
Tracked in **`POST_LAUNCH_BACKLOG.md`** — none are required for v1 operation:
mobile app, ZKTeco hardware integration, push notifications, email service,
dedicated Accountant & Librarian roles, monitoring/observability, AI tutor.

---

## Part C — File inventory (whole migration)

### Files added
**Backend**
- `app/core/single_school.py` — single-org resolver
- `app/schemas/attendance.py` — attendance contracts
- `app/services/attendance.py` — ingestion service (ZKTeco adapter port)
- `app/routers/modules/attendance.py` — attendance API
- `alembic/versions/002_add_attendance_events.py` — attendance migration
- `tests/test_attendance.py`, `tests/test_single_school_auth.py`
- `scripts/backup_db.py` — backup utility
- `entrypoint.sh` — migration-on-boot entrypoint

**Frontend**
- `hooks/useAttendance.ts`, `hooks/useNotifications.ts`
- `components/attendance/shared.tsx`
- `app/(dashboard)/dashboard/my-children/attendance/page.tsx` (Parent)
- `app/(dashboard)/dashboard/my-classes/attendance/page.tsx` (Teacher)
- `app/(dashboard)/dashboard/modules/school/attendance/dashboard/page.tsx` (Admin)

**Infra / docs**
- `docker-compose.prod.yml`, `nginx.conf`, `.env.production.example`
- `BACKUP.md`, `DEPLOYMENT.md`, `GO_LIVE_CHECKLIST.md`, `OPERATIONS_RUNBOOK.md`
- `PRINCIPAL_USER_GUIDE.md`, `TEACHER_USER_GUIDE.md`, `PARENT_USER_GUIDE.md`
- `RELEASE_NOTES_v1.0.md`, `POST_LAUNCH_BACKLOG.md`

### Files modified
**Backend:** `app/config.py`, `app/routers/auth.py`, `app/schemas/auth.py`,
`app/services/onboarding.py`, `app/main.py`, `app/models/notification.py`,
`app/models/modules/school.py`, `app/models/role.py`,
`scripts/seed_fairview_school.py`, `requirements.txt`, `tests/conftest.py`,
`tests/test_usage_tracking.py`, `Dockerfile`.
**Frontend:** `lib/api.ts`, `lib/seo.ts`, `lib/import/presets.ts`, `next.config.js`,
`app/layout.tsx`, `app/robots.ts`, `app/(auth)/login/page.tsx`,
`app/(auth)/register/page.tsx`, `app/(dashboard)/dashboard/my-children/page.tsx`,
`app/(dashboard)/dashboard/home/AdminHome.tsx`, `hooks/useAuth.ts`,
`components/layout/Sidebar.tsx`, `components/layout/GlobalSearch.tsx`,
`components/loading/Splash.tsx`, `components/marketing/IndustryLanding.tsx`,
`app/erp-for-schools/page.tsx`, `.env.example`.
**Root:** `docker-compose.yml`, `.env.example`.

### Files removed
**Frontend (user-facing hospital/business surface):**
- `app/(dashboard)/dashboard/modules/hospital/` (all pages + layout + import)
- `app/(dashboard)/dashboard/modules/business/` (all pages + layout + imports)
- `app/hospital-management-system/`, `app/business-management-erp/` (marketing)
- `hooks/useHospital.ts`, `hooks/useBusiness.ts`

**Backend:** none removed — hospital/business code is **deprecated and retained**
(unmounted, unreachable) per the reversible deprecation strategy.

---

## Quality gates at freeze
- Backend: **236 passed / 2 pre-existing** (unrelated legacy plan-enforcement).
- Frontend: production build ✅ (standalone) · `tsc --noEmit` ✅.
- Attendance service, single-school auth, and parent-notification copy verified by tests.
