# Fairview School Portal — Post-Launch Backlog

**Future enhancements only.** None are required for v1.0 operation. Each item
requires a **new, authorised project phase** — the v1.0 codebase is frozen.
Items are written to build on the existing, deliberate extension points.

---

## 1. Mobile application
A parent/teacher/student mobile app (iOS/Android).
- **Why:** parents live on mobile; attendance alerts and fee payments suit a phone.
- **Build on:** the existing JSON API (`/api/v1/*`) and JWT auth; reuse the
  domain-gated login and `/me/contexts` role model.
- **Scope:** parent attendance + alerts + fees first; then teacher attendance
  capture; offline-friendly for low connectivity.

## 2. ZKTeco hardware integration
Connect the school's existing ZKTeco biometric devices to the portal.
- **Why:** automate check-in/out instead of manual entry.
- **Build on:** the **already-built adapter port** — `AttendanceIngestionService.ingest()`
  and `POST /api/v1/attendance/events/ingest`. A new `ZKTecoAdapter` maps device
  punches → `AttendanceEventIn` and pushes them; dedup, daily-record derivation,
  audit, and parent notifications already happen server-side.
- **Scope:** device polling/push connector, a **device-token/API-key** auth scheme
  for the ingest endpoint, device registry, and reconciliation/monitoring.

## 3. Push notifications
Real-time push (web push / mobile push) for attendance and announcements.
- **Why:** instant delivery without the portal open.
- **Build on:** the notification **payload is already outbox-ready** (carries
  student, event type, time). Add a delivery worker + device-token storage.
- **Scope:** web push (VAPID) and/or FCM/APNs; per-user channel preferences.

## 4. Email service implementation
Transactional email (password resets, invites, digests, receipts).
- **Why:** v1 has **no** email sender — credentials are managed manually today.
- **Build on:** `SMTP_*`/`FROM_EMAIL` settings already exist (currently inert).
- **Scope:** an email service (SMTP or provider API), templates, password-reset
  and invite flows, and a queued/retrying sender.

## 5. Accountant role
A dedicated finance role distinct from the Principal/Admin.
- **Why:** separate bursar/finance duties from full administration.
- **Build on:** the `payments:*` permission namespace already exists and is
  enforced; v1 grants it to admin/management.
- **Scope:** an `accountant` role preset (payments + read-only academics) **and**
  role-switcher/home support in `/me/contexts` + sidebar so the role renders a
  proper finance view.

## 6. Librarian role
A dedicated library role.
- **Why:** let library staff manage loans without broad school write access.
- **Build on:** existing library module + RBAC.
- **Scope:** a `librarian` role and (ideally) a finer `library:*` permission
  scope so it isn't tied to the coarse `school:write`, plus role-switcher support.

## 7. Monitoring and observability
Production monitoring, alerting, and error tracking.
- **Why:** v1 ships health checks + structured logs + in-process denial counters,
  but no external monitoring/alerting.
- **Scope:** uptime monitor + alerts on `/health`; centralised log shipping with
  retention; error tracking (e.g. Sentry) on API + web; DB and disk metrics;
  **backup-success alerting** (page if a nightly backup is missing/0-byte);
  optional dashboards.

## 8. AI tutor integration
AI-assisted learning and analytics.
- **Why:** strategic differentiator; aligns with the platform's AI-readiness.
- **Build on:** existing AI assistant scaffolding and student academic data
  (grades, CBT, attendance) — all already in the school data model.
- **Scope:** AI tutor for students, performance analytics, learning
  recommendations, and academic-risk prediction, with clear data-privacy and
  guardrail controls.

---

### Also noted from the readiness audit (smaller follow-ups)
- Remove deprecated hospital/business backend code once permanently confirmed
  unneeded (currently retained, unmounted, reversible).
- Remove now-inert multi-tenant admin endpoints (`/organizations/*`, SaaS billing)
  if zero legacy surface is desired.
- Cosmetic: `extracare-auth` localStorage key, `package.json` name, unused
  `authApi.register`/`useRegister`.
- Triage the 2 pre-existing, unrelated plan-enforcement test failures.
