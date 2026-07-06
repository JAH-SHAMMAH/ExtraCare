# Fairview School Portal — Post-Launch Backlog

**Future enhancements only.** None are required for v1.0 operation. Each item
requires a **new, authorised project phase** — the v1.0 codebase is frozen.
Items are written to build on the existing, deliberate extension points.

> **Exception:** the section immediately below is **not** a future enhancement —
> it is a functional gap that should be fixed **before launch**.

---

## ⚠️ PRE-LAUNCH — HIGH PRIORITY (functional bug, not cosmetic)

### `GET /school/classes` — ✅ RESOLVED (2026-07-05)
Implemented the full class CRUD in `backend/app/routers/modules/school.py`:
`GET /school/classes` (list, paginated + search, `school:read`), `GET /school/classes/{id}`,
`POST`/`PATCH`/`DELETE` (`school:write`). Responses map ORM columns to the frontend
`SchoolClass` shape (`level→grade_level`, `max_capacity→capacity`,
`teacher_id→class_teacher_id` + resolved `class_teacher_name`, computed
`student_count`, `is_active=true`). Added the missing `section` column
(migration `032_add_class_section`) so the UI's section field persists instead of
silently no-op'ing. Delete is guarded (409) while students are enrolled. Proven
live: `GET /school/classes` returns all 14 Fairview classes with real counts/teacher.
Tests in `backend/tests/test_school_classes.py`. Original report kept below.

<details><summary>Original bug report</summary>

**Symptom:** any screen that lists classes shows an empty list (empty dropdowns,
"no classes"), even though classes exist.

**Root cause:** the frontend's `useClasses` hook (`frontend/hooks/useSchool.ts`)
and `schoolApi.classes.*` (`frontend/lib/api.ts`) call `GET /school/classes`
(plus create/update/delete), but **no such route is implemented**. The school
router (`backend/app/routers/modules/school.py`, prefix `/school`) has
students / teachers / timetable / lessons — but nothing for classes. The call
404s, so `useClasses` returns nothing. The only class-list route in the app is
`/sms/classes` (SMS targeting) and the finance-scoped `/finance/classes` added
for Fee Assignment.

**Why it's not cosmetic:** classes genuinely exist (14 for Fairview: Nursery 1–2,
Primary 1–6, JSS 1–3, …, each ~35 students) and are referenced by students —
they simply cannot be listed through the endpoint the UI expects. **Every**
`useClasses` consumer is affected, e.g. enrollment/admissions and any
class-scoped picker. (Fee Assignment was unblocked separately via
`GET /finance/classes`, so that one page works; the general gap remains.)

**Fix:** implement `GET /school/classes` (list, gated `school:read`) returning
classes mapped to the frontend `SchoolClass` shape — `id, name,
level→grade_level, max_capacity→capacity, teacher_id→class_teacher_id` (+ resolved
`class_teacher_name`), computed `student_count`, `academic_year`. Add
`POST/PATCH/DELETE /school/classes` too if a class-management UI is wanted (the
frontend `schoolApi.classes` already references them).

**RBAC note:** `school:read` covers managers/admins but **not accountants** (they
hold no `school:*` perms). If a class list is needed on a finance screen for
accountants, mirror the `/finance/classes` (`payments:write`) approach used by
Fee Assignment rather than gating on `school:read`.

**Priority:** HIGH — fix before go-live; empty class pickers block enrollment and
any class-scoped workflow.

</details>

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

### Known UI gaps (found during Finance stub build-out)
- **Payroll payslip — no free-text staff fallback.** `PayslipInput` accepts
  `staff_name` without `staff_user_id`, and the create filter already allows a
  name-only line, but the payslip row UI (`payroll/page.tsx`) offers only the
  `EntityPicker` — no text input. Same class of gap as the Bonus/Reduction Pack
  bug, **but not currently blocking anyone**: the Payroll picker renders fine
  (it's in a grid, not an `overflow-hidden` wrapper, so it isn't clipped). Fix:
  add a free-text "Staff name" input to the slip row, mirroring the Bonus/
  Reduction Pack create form. Frontend-only, no backend change.
- **Petty-cash over-budget warning uses all-time spend, Budget page uses
  period-scoped spend.** After Budget Management gained date windows, the live
  over-budget warning shown when recording a petty-cash entry
  (`finance_ops.record_petty_cash` → `_account_spent` with no window) still
  measures **all-time** spend on the account, while the Budget page now shows
  spend **scoped to the budget's start/end dates**. Same account can therefore
  show two different "spent" figures when a budget window is active. **Not a
  correctness bug** — petty-cash's soft warning isn't wrong, just inconsistent
  with the new page. Fix (if desired): have the petty-cash warning look up the
  account's budget and reuse its window. Left untouched to avoid changing the
  tested petty-cash path.
- **Accounts Setup defaults — not yet consumed by every create form.** The
  `OrgFinanceSettings` defaults (cash / fees-income / receivable / expense) are
  pre-filled via `useFinanceSettings` on the **Requisitions Request Form** and the
  **Bonus/Reduction Pack** form. The remaining finance create forms still make you
  pick accounts manually and should adopt the same one-line `useFinanceSettings`
  pre-fill (frontend-only, low risk):
  • Payroll (`expense_account_id`, `net_account_id`, `deductions_account_id`)
  • Invoices (`receivable_account_id` + per-line `income_account_id`)
  • Petty Cash (`expense_account_id`, `cash_account_id`)
  • Cash Transactions (`cash_account_id`, `counter_account_id`)
  • Manual Journal (per-line accounts)
  (Salary Advance's approve step already auto-picks a cash account server-side, so
  it's lower priority.) Not a bug — the defaults are correct and optional
  everywhere; this is consistency of the convenience pre-fill.

### Known integration gaps — DELIBERATE deferrals (feature ships; integration pending)

These are working features that were intentionally built **decoupled** from a
neighbouring system to keep blast radius small. They are recorded here so a
deliberate boundary does not silently become a forgotten one. None is a bug.

- **Appointment Manager → Payroll (no auto-feed).** `StaffAppointment` records a
  staff member's grade/salary/effective-date history, but the current/active
  appointment's salary is **not** automatically applied to payroll runs — payroll
  amounts are still entered per-run. Integration: when building a payroll run,
  pre-fill each staff member's gross from their latest active `StaffAppointment`.
  Records-only today, by design.
- **Salary Advance → Payroll (no auto-deduction).** A disbursed advance is repaid
  **manually** via the repay endpoint; repayments are **not** auto-deducted from
  payroll runs. Integration: on payroll approval, net outstanding advance
  repayments against pay and post the repayment automatically. Manual repay +
  shared ledger is what ships today.
- **Warehouse — full multi-location (POS/store location-aware) deferred.** The
  Warehouse module tracks per-location stock, transfers and issues **independently**
  of the sellable `StoreItem.quantity` (the store page + POS still sell from the
  single total — deliberately untouched, zero regression risk). The "full" option
  makes per-location stock the single source of truth: the store page AND the POS
  become location-aware (choose which warehouse to buy into / sell from), and
  `StoreItem.quantity` becomes the sum across locations. That rewires shipped store
  + POS code, so it's its own future unit — pick it up only if a real need justifies
  the rewire.
- **Store Pickup — collection RBAC. ✅ RESOLVED — `collect` opened to `store:sell`.**
  Point config + ticket create/cancel/delete stay on `payments:write` (finance-clerk
  gate). `POST /finance/pickups/{id}/collect` accepts **either `store:sell` OR
  `payments:write`** (via the reusable `AnyPermissionChecker` in `app/core/permissions.py`)
  — handing an item over is a daily, no-money/no-ledger till-counter task usually done
  by the same cashier who rang up the sale, so requiring them to flag down finance
  staff was friction, not a real boundary. Additive change: a **manager**
  (`payments:write`, no `store:sell`) keeps collect access; a **cashier** (`store:sell`,
  no `payments:write`) gains it. No further work — noted here as the decision record.
- **Sales Monitor — store sales only, not tuckshop.** The `/finance/store/sales-summary`
  analytics cover **store POS sales** (`StoreSale`), which is where the real data
  is. The stub also mentions **tuckshop** sales — `TuckshopTransaction` is a
  separate model (`app/models/payment.py`) with its own flow, not yet folded into
  the summary. Follow-up: add a tuckshop revenue section (or merge tuckshop txns
  into the same period aggregates) once tuckshop is in real use.
- **Store Front Desk (POS) v1 — revenue + stock only; COGS + till deferred.**
  A sale posts revenue (Dr Cash / Cr Store Sales) and reduces stock, but does NOT
  post **cost of goods sold** (Dr COGS / Cr Inventory at `cost_price`) — so gross
  margin isn't in the ledger yet. Also **no till reconciliation / cash-up session**
  (open/close float, count cash vs recorded sales). And "Print receipt" is a plain
  `window.print()`, not a formatted thermal-receipt template. All deliberate v1
  scope cuts.

  **✅ RESOLVED — dedicated `store:sell` (Cashier) permission shipped.** The POS
  sale POST + void now gate on the narrow `store:sell` instead of the broad
  `payments:post` (which also approves payroll/discounts/ledger posts). A **Cashier**
  role (`payments:read` + `store:sell`, NOT `payments:post`) lets junior till staff
  ring up + void sales without the power to approve salaries. `store:sell` was
  granted to org_admin (`store:*`) and accountant so existing operators keep the
  till; new orgs get the cashier preset at seed, existing orgs got the role +
  grants via migrations 025/026. Store **purchase** stays on `payments:post` (that's
  inventory buying, a broader financial posting — intentionally not moved). COGS,
  till reconciliation and receipt-printing remain deferred (above).
- **Payment Gateways — ✅ BUILT (encryption service + per-org config + consumption).**
  Encryption-at-rest service shipped (`app/services/crypto.py`, AES-256-GCM,
  versioned keyring, `EncryptedStr`). Gateway CRUD is org_admin-only
  (`payment_gateways:*` namespace) and stores secrets ENCRYPTED into
  `TenantPaymentSettings.encrypted_*` (we converged onto that model — the one the
  billing resolver consumes — and dropped the duplicate `payment_gateways` table).
  `payment_resolver.resolve_for_org` now decrypts the per-org Paystack secret and
  binds the provider to it (live fee payments use the school's own key, not the env
  key). Webhook secret resolution decrypts too (tolerates legacy raw values).
  Remaining follow-ups below.

- **Resolver decrypt-failure — ✅ RESOLVED — now fails loud (503).** If a per-org
  secret is stored but can't be decrypted, `resolve_for_org` raises the dedicated
  `PaymentConfigError` and both `school_payments.py` resolver call sites return a
  hard **503** instead of falling back to the platform account. This prevents a
  school's fees from silently routing to the platform Paystack key on a key
  misconfig. Proven by `test_initiate_hard_fails_when_per_org_secret_undecryptable`
  (HTTP 503) + `test_resolver_hard_fails_on_undecryptable_secret` (unit).

### TICKET — Wire Remita to per-org credentials — ✅ RESOLVED (2026-07-05)
  Remita now consumes the school's OWN credentials configured in the Payment
  Gateways UI (falling back to env when unconfigured). Done:
    - `RemitaCredentials` (merchant id + service-type id + API key + base url) +
      `remita.resolve_credentials(db, org_id)`: loads the active `TenantPaymentSettings`
      REMITA row, decrypts the API key (`encrypted_secret_key`), reads merchant/
      service-type from `metadata`; **fails loud (`PaymentConfigError` → 503)** if a
      config exists but the key can't be decrypted; env fallback when unconfigured.
    - `generate_rrr` / `query_status` take `creds` (no globals); threaded through the
      `/payments/remita` router (initiate/verify/webhook + the redirect `payment_url`
      now points at the resolved merchant/host). Webhook logs + skips on misconfig
      (no 503 — Remita retries).
    - Gateway CRUD + UI capture Remita's `merchant_id` + `service_type_id` (metadata,
      non-secret) and relabel the secret field to "API key"; the api key is encrypted.
    - Tests: per-org creds used (not env), env fallback, decrypt-failure → hard error,
      CRUD stores/exposes the 3-part cred. (`test_remita.py`, `test_payment_gateways.py`.)
  **Note:** the hosted-redirect URL format (`/remita/onepage/...`) is still a
  best-reconstruction (GO-LIVE CHECKLIST in `remita.py`) — confirm against a real
  Remita account. That's a separate go-live verification, not blocking this wiring.

### TICKET — Add a Flutterwave provider adapter (currently STORABLE VIA UI, NOT CONSUMED)
  **Status:** storable via UI, **not consumed** — do not assume parity with Paystack.
  `PaymentProvider.FLUTTERWAVE` exists and creds can be saved in the UI, but there is
  **no Flutterwave provider adapter** and nothing reads the stored config.
  **Scope of the work:**
    - Build a `FlutterwaveProvider` (mirror `app/services/paystack.py`: initialize
      transaction, verify, webhook signature) against Flutterwave's API.
    - Extend `payment_resolver.resolve_for_org` (or a provider factory) to build the
      right provider class from `TenantPaymentSettings.provider`, decrypting the
      per-org secret — so any configured provider is consumed, not just Paystack.
    - Wire the fee-payment initiate/verify/webhook path to the resolved provider.
    - Tests: per-org Flutterwave secret used; webhook verification.

### TICKET — Remove the legacy raw webhook-secret compatibility shim
  **Status:** shim live, needs an expiry trigger (don't let it live forever silently).
  `school_payments.py` webhook-secret resolution tolerates a LEGACY raw (unencrypted)
  `encrypted_webhook_secret` via `crypto.looks_like_token()` — new secrets are
  encrypted, old raw ones still work. It now emits
  `_logger.warning("webhook.paystack.legacy_raw_webhook_secret org=%s …")` every time
  the raw path is hit, so we have a **metric/signal** for when it's safe to remove.
  **Removal plan:** (a) monitor that log — once it's silent across a full billing
  cycle, OR (b) run a one-off management command that re-encrypts any remaining raw
  `encrypted_webhook_secret` values (decrypt-check → `crypto.encrypt`), THEN delete
  the `else: tenant_secret = stored` branch so a non-token value is treated as
  invalid rather than trusted. Until then the shim stays for backward-compat.
