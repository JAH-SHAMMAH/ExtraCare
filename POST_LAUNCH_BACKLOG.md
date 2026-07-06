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
- **Accounts Setup defaults — ✅ pre-fill extended (2026-07-06).** The
  `OrgFinanceSettings` defaults (cash / fees-income / receivable / expense) now
  pre-fill via `useFinanceSettings` on **Payroll** (expense → net/cash), **Invoices**
  (receivable + each line's income, incl. new lines), **Petty Cash** (expense + cash),
  and **Cash Transactions** (cash + a direction-aware counter: receipt→income,
  payment→expense) — in addition to the existing Requisitions + Bonus/Reduction forms.
  Fills only empty fields (never overrides a manual pick) and re-seeds on reset so the
  next entry is pre-filled too. Payroll's optional **Deductions Payable** is left blank
  (a liability with no default).
  **Deliberately SKIPPED — Manual Journal (`direct-posts`) + Direct Transfer.** These
  are freeform double-entry: each line's account is intentionally chosen by the
  poster, so there is no meaningful single default to pre-fill — auto-filling a blank
  journal line with "the cash account" would be actively misleading, not helpful.
  (Salary Advance's approve step already auto-picks a cash account server-side.)
  Not a bug anywhere — this was consistency of the convenience pre-fill.

### ⚠️ AUDIT FINDINGS (2026-07-06) — built/storable but NOT consumed by the live UI flow

Found during a full "storable-but-not-consumed" audit. Unlike the deliberate
deferrals below, these are places where a feature looks usable but the live path a
user hits doesn't actually consume it.

- **Paystack + Flutterwave parent fee flow was UI-ORPHANED — ✅ RESOLVED (2026-07-06).**
  A new unified **invoice-based** parent router `app/routers/fee_payments.py`
  (`/payments/fees`) exposes `GET /providers` (returns whichever gateways the school
  actually configured — per-org `TenantPaymentSettings`, else platform-env fallback),
  `POST /initiate` and `GET /verify` for the card providers (Paystack/Flutterwave) via
  the resolver factory, settling the invoice on success (Dr `<provider> / Bank` / Cr
  Receivable). The parent payments page now shows a **provider selector** built from
  `/providers` (only configured gateways, no fixed list) and routes Remita →
  `/payments/remita/*`, card → `/payments/fees/*`. **LIVE-VERIFIED**: configured a
  per-org Flutterwave gateway + a posted invoice for a real parent's child, drove the
  actual parent HTTP flow, and got a **real Flutterwave checkout link** for that
  invoice; `/providers` correctly returned `["flutterwave"]`.
  **Leftover to clean up:** the older AMOUNT-based Paystack flow `/school/payments/parent/*`
  (`school_payments.py`) is now doubly-unused (parent UI uses `/payments/fees` +
  `/payments/remita`) — safe to remove, along with its dead `outstanding-fees`
  (paid_amount=0) / `student_name=None` TODOs. Left in place for now (has tests +
  the Flutterwave webhook lives there); removal is a separate cleanup unit.

### TICKET — Wire a real SMS provider (currently mock-only; UI now says so)
  **Status:** ⚠️ mock-only — the Bulk SMS page now shows a "Mock mode — messages are
  NOT delivered to real phones" banner (honest, mirrors the Flutterwave treatment).
  `app/services/sms.py` registers `{"mock": MockSmsProvider()}` and `get_provider`
  defaults to `mock` (env `SMS_PROVIDER`). Admins compose + "send" campaigns, spend
  units, and see delivered/DLR status, but nothing reaches a phone; the DLR webhook is
  a stub. **BLOCKED ON A BUSINESS DECISION:** pick a provider (Termii vs Twilio vs
  Africa's Talking vs Termii — regional pricing/deliverability). Once chosen:
    - implement one real `SmsProvider` (the `Protocol` + registry are ready — "one line
      in settings plus the adapter"), add its creds to config, set `SMS_PROVIDER`;
    - implement the DLR webhook (`sms.py`) for real delivery receipts;
    - remove the mock-mode banner (or gate it on `SMS_PROVIDER == "mock"`).

- **Dead endpoint: `GET /school/payments/parent/outstanding-fees/{id}`** returns a
  per-category fee breakdown with `paid_amount` hardcoded to `0` (TODO) — but it's
  part of the UI-orphaned Paystack flow above, so it's **not a live display bug**,
  just dead code to remove or finish if that flow is ever wired to the UI. Same for
  the `student_name=None` TODO in the transactions list and the now-dead
  `except NotImplementedError` branches (the resolver no longer raises it).

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
  **LIVE SANDBOX VERIFIED (2026-07-06):** ran the real HTTP round-trip against
  Remita's demo host (not mocked): `generate_rrr` returned a valid RRR
  (statuscode 025), `query_status` returned the transaction status (021 pending),
  `is_paid()` read it correctly. **This caught a real bug:** the shipped demo host
  `remitademo.net` now 302-redirects to `demo.remita.net`, and the API POST doesn't
  follow redirects — so every Remita init was silently failing on the default
  config. Fixed the `REMITA_BASE_URL` default to `https://demo.remita.net`.
  **Still NOT verified (narrower now):** whether the reconstructed hosted-redirect
  URL (`/remita/onepage/{merchant}/{rrr}/payment.spa`) actually renders Remita's
  payment page in a browser — that's a click-through/UX check (GO-LIVE CHECKLIST in
  `remita.py`), separate from the API round-trip which is now proven.

### TICKET — Flutterwave provider adapter — ✅ BUILT + LIVE-VERIFIED (2026-07-06)
  `FlutterwaveProvider` (`app/services/flutterwave.py`, Standard Checkout / v3
  `/payments`) is registered in the factory (`SUPPORTED_PROVIDERS` now
  `{PAYSTACK, FLUTTERWAVE}`), resolves per-org creds from `TenantPaymentSettings`
  (API key encrypted in `encrypted_secret_key`, verif-hash in `encrypted_webhook_secret`),
  decrypts + fails loud (`PaymentConfigError` → 503) on decrypt failure — same as
  Paystack/Remita. Wired into the school-payments fee path (initiate/verify are now
  provider-aware: `tx.provider` + the FK config row reflect the resolved provider,
  each provider uses its OWN redirect URL). Webhook handler
  `POST /api/v1/school/payments/webhook/flutterwave` verifies the `verif-hash` header
  against the org's secret hash and REJECTS a mismatch (401), then re-verifies with
  Flutterwave before recording.
  **PROVEN LIVE** (real HTTP vs Flutterwave TEST API): `initialize_payment` returns a
  real hosted checkout link; the full per-org path (encrypted store → factory decrypt
  → build → live init) works; and — after paying a test checkout link with a test card
  (2026-07-06) — `verify_transaction` against the **real completed transaction**
  returned normalised `status="success"` with the real id/amount and `metadata.org_id`
  intact (Flutterwave raw "successful" → "success"). So the exact shape the record path
  keys on is confirmed live.
  **STILL NOT verifiable without a public server:** actual webhook DELIVERY from
  Flutterwave (URL unregistered, no public endpoint). The verif-hash signature check is
  unit-tested (401 on mismatch / 200 on match) but has never been hit by a real
  delivery — see the go-live item below.

### GO-LIVE — register the Flutterwave webhook URL (deferred; no public server yet)
  The webhook handler is built + signature-verifying, but the URL is NOT registered on
  the Flutterwave dashboard (no public endpoint yet). On deploy: Flutterwave dashboard
  → Settings → Webhooks → set the URL to `https://<host>/api/v1/school/payments/webhook/flutterwave`
  and set the **Secret Hash** to the same value stored per-org (or the platform env
  `FLUTTERWAVE_WEBHOOK_SECRET_HASH`). Also switch keys TEST → LIVE (FLWSECK_TEST- →
  FLWSECK-). Same class of go-live item as the Remita checklist. Until registered, the
  parent VERIFY endpoint (on redirect return) is the payment-confirmation path; the
  webhook is the async backup.

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
