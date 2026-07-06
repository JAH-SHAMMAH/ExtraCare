# Effective Permission Matrix — Features built in Batches 1–3

Read-only artifact (no behavioural change). Shows, per **system role**, the
effective **read** / **write** access to each shipped feature, after the
`User.has_permission` resolution rules are applied.

Roles (school workspace system presets): **Admin** = org_admin · **Mgr** =
manager · **Tch** = teacher · **Staff** = staff · **View** = viewer ·
**Std** = student · **Par** = parent.

`✓` = allowed · `✗` = denied.

## How resolution works (so the grid is auditable)

`has_permission(p)` is true when ANY of these hold://
1. **exact** — `p` is literally in the role's grant list;
2. **namespace wildcard** — `"<ns>:*"` is granted (e.g. Admin's `school:*`
   covers `school:anything[:anything]`);
3. **two-part hierarchy** — for a 3-part scope `ns:feature:action`, a broad
   `ns:action` grant covers it. So `school:read` ⇒ every `school:*:read`, and
   `school:write` ⇒ every `school:*:write`.

Consequences that drive the grid below:
- **Admin** holds `school:*` (+`school_admin:*`,`payments:*`,`hr:*`) → everything school.
- **Mgr** holds `school:read`+`school:write` (+`school_admin:*`,`hr:write`).
- **Tch** holds `school:read`+`school:write` (no `school_admin`, no `hr:write`).
- **Staff** holds `school:read` only (no `school:write`) → school read-only.
- **View** holds `school:read` only → school read-only.
- **Std/Par** hold ONLY narrow self-service scopes (e.g. `school:reports:read`
  for their own card) — never the broad `school:read`/`:write`, so every
  staff-facing feature below resolves to `✗` for them.

> Two-part namespaces (`hr:write`, `medical:read`) have NO hierarchy — only
> exact or `<ns>:*` grants them. That is deliberately how confidential surfaces
> are kept off the broad `school:read` net.

## Matrix

| # | Feature | Required scope | Admin | Mgr | Tch | Staff | View | Std | Par |
|---|---------|----------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Parents Directory — read | `school:parents:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 1 | Parents Directory — write | `school:parents:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| 2 | Staff Assessment — read+write | `hr:write` | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 3 | Talent Pool — read+write | `hr:write` | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 4 | Admissions & Enquiries — read | `school:admissions:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 4 | Admissions & Enquiries — write | `school:admissions:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| 4 | Admissions — **admit→Student** | `school:students:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| 5 | Entrance Exams — read | `school:admissions:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 5 | Entrance Exams — write | `school:admissions:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| 6 | Promotion Manager — read | `school:students:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 6 | Promotion Manager — write/revert | `school:students:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| 7 | Transfer Manager — read | `school:students:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 7 | Transfer Manager — write | `school:students:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| 8 | Subject Selection — read | `school:subjects:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 8 | Subject Selection — write | `school:subjects:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| 9 | Mark Books & Transcripts — read | `school:grades:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 9 | Mark Books & Transcripts — write | `school:grades:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| 10 | Report Workflow — read+write | `school:reports:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| 11 | Merit & Awards — read | `school:behaviour:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 11 | Merit & Awards — write | `school:behaviour:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |

### Notes / intentional design points
- **Std/Par are `✗` everywhere above.** They hold only their own self-service
  scopes (`school:reports:read` = their report card, `school:attendance:read` =
  their child, etc.), which are served by separate ownership-scoped endpoints —
  not by any feature in this matrix.
- **Report Workflow is gated on `:write` even to view** on purpose: Std/Par hold
  `school:reports:read` for their own card, so gating the admin approval tool on
  `read` would have leaked it to them. Using `write` keeps it staff-only.
- **Staff vs Teacher**: identical *read* across school features (both ride
  `school:read`); they diverge on *write* (only Tch has `school:write`).
- **`hr:write` features (Staff Assessment, Talent Pool)** are Admin/Mgr only —
  Tch holds `hr:read` (self-service My-HRM/My-Leave marker) which does NOT
  satisfy `hr:write` (no hierarchy on 2-part scopes).

### Batch 4 — Pastoral, Boarding & Health (shipped + tested)

**Medicals** uses a **top-level `medical`** namespace (NOT `school:medical:*`),
so the `school:read` hierarchy does NOT reach it — verified by
`test_medical.py::test_teacher_cannot_read_or_write_medical`.

| Feature | Required scope | Admin | Mgr | Tch | Staff | **Nurse** | Std | Par |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Medicals — read | `medical:read` | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Medicals — write | `medical:write` | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Hostel / Boarding — read | `school:hostel:read` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Hostel / Boarding — write | `school:hostel:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Exeat — request/read | `school:hostel:read/write` | ✓ | ✓ | ✓ | r/o | ✗ | ✗ | ✗ |
| Exeat — **approve / reject** | `school_admin:write` | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mentor Reports — read | `school:behaviour:read` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Mentor Reports — write | `school:behaviour:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |

- **Nurse** role = `medical:read`+`medical:write`+`hr:read` ONLY (no `school:*`),
  so it sees Medicals (+ its own self-service HR) and nothing else school-side.
- The nurse `✗` on hostel/exeat/mentor is correct — those ride `school:*`, which
  the nurse does not hold.
- Manager is intentionally NOT granted `medical` ("admin only" per request);
  flip by adding `medical:read/write` to the manager preset.

## Batch 5 — Finance & Accounting (first half) + new `Accountant` role

Segregation of duties: **`payments:write`** drafts, **`payments:post`** posts to
the ledger. The new **Accountant** role is finance-only (no `school:*`).

| Feature / action | Required scope | Admin | Mgr | **Acct** | Tch | Staff | Std | Par |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Finance pages — view (Accounts/Invoices/Payroll) | `payments:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Create draft (account/invoice/payroll) | `payments:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Post / pay / void / approve / lock period** | `payments:post` | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Pay child's fees (existing) | `payments:read` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |

- **Manager drafts but cannot post** (`payments:post` not granted) → the default
  two-person flow is *manager creates → admin/accountant posts*.
- **Payroll** adds a code-level rule on top of RBAC: `approved_by != created_by`,
  so even a user holding both `write`+`post` (admin/accountant) cannot run *and*
  approve the same payroll — verified by
  `test_finance_features.py::test_payroll_creator_cannot_self_approve`.
- Finance pages are gated on `payments:**write**` (not read) so **parents** (who
  hold `payments:read` to pay fees) never see the ledger/payroll.
- **Accountant** role = `payments:read/write/post`+`hr:read` only — sees Finance
  and nothing else school-side (mirrors how the nurse is scoped to medical).

### Batch 5 second half (Petty Cash / Cash / Store) — same SoD scopes
- **Recording a posting** (petty-cash disbursement, cash receipt/payment, stock
  purchase) → `payments:post` (accountant/admin). **Manager cannot** record these
  (no `payments:post`).
- **Setup / non-financial** (budgets, store items, stock issue/adjust) →
  `payments:write` (manager/accountant/admin).
- All gated on `payments:write` for page view → parents (fees `payments:read`)
  never see them. Guard inheritance proven per feature in `test_finance_ops.py`.

## Batch 6 money features — Wallet / PocketMoney / Cooperative + new `wallet:spend`

The dedicated, self-limiting **`wallet:spend`** scope (new `wallet` namespace,
outside the `school:read` hierarchy) lets till staff draw a student's OWN wallet
down to income — and nothing else.

| Capability | Required scope | Admin | Mgr | Acct | **Till (staff)** | Par |
|---|---|:---:|:---:|:---:|:---:|:---:|
| View wallets / cooperative; create wallet/member; set spend limit | `payments:write` | ✓ | ✓ | ✓ | ✗ | ✗ |
| **Top-up / withdraw / cooperative contribute+payout** (move cash) | `payments:post` | ✓ | ✗ | ✓ | ✗ | ✗ |
| **Record a spend** (draw OWN wallet → income, no-overdraw, period-locked) | `wallet:spend` | ✓ | ✓ | ✓ | ✓ | ✗ |
| Top-up / post invoice / payroll / arbitrary GL entry | (various `payments:*`) | ✓ | partial | ✓ | **✗** | ✗ |

- A `wallet:spend`-only holder (till) **cannot** top-up, withdraw, move cash, or
  post invoices/payroll — proven by `test_wallet.py::test_wallet_spend_scope_is_constrained`.
- Balances are derived from the subledger; **GL liability ↔ subledger reconciles**
  (`test_wallet_reconciliation_ties_out`). No stored balance can drift.
- Wallet float + cooperative fund are **liabilities** — income is recognised only
  when a wallet is spent.

## Batch 6 non-financial — Calendar / Facility / Visitor (safeguarding)

| Feature | Required scope | Admin | Mgr | Tch | Staff | Std/Par |
|---|---|:---:|:---:|:---:|:---:|:---:|
| Calendar & Planner — read/write | `school:read` / `:write` | ✓ | ✓ | ✓ | r/o | ✗ |
| Facility Management (+ bookings) | `school_admin:read` / `:write` | ✓ | ✓ | ✗ | ✗ | ✗ |
| Visitor Management (sign-in/out, **child collection**) | `school_admin:read` / `:write` | ✓ | ✓ | ✗ | ✗ | ✗ |

- **Visitor Management is a safeguarding surface**: visitor + collection mutations
  are written to the immutable audit log; records are **soft-deleted only**
  (preserved, never silently removed); a **child collection requires + captures
  the authorising staff member** (`authorized_by`). Proven in `test_operations.py`.
- Facility bookings are protected by a **double-booking guard** (overlap → 409).

## Batch 7 — Administration & Platform (settings:* — admin only)

Platform/admin config sits on the **core `settings`** namespace, which only
**`org_admin`** holds (`CORE_ADMIN_PERMISSIONS`). Manager/teacher/staff/student/
parent presets do **not** include `settings:*`, so all six admin surfaces are
admin-only — verified in `test_platform.py::test_platform_rbac_settings_only`.
A few per-user actions are intentionally broader so end users can use the app.

| Capability | Required scope | Admin | Mgr | Tch | Staff | Std/Par |
|---|---|:---:|:---:|:---:|:---:|:---:|
| School Setup (sessions/houses/bands) — read/write | `settings:read` / `:write` | ✓ | ✗ | ✗ | ✗ | ✗ |
| Biometric devices / enrollments / quarantine — read/write | `settings:read` / `:write` | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Biometric punch ingest** (`POST /biometric/ingest`) | `settings:write` †  | ✓ | ✗ | ✗ | ✗ | ✗ |
| Custom Fields (defs + values) — read/write | `settings:read` / `:write` | ✓ | ✗ | ✗ | ✗ | ✗ |
| Voting — create / close / delete poll | `settings:write` | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Voting — cast a vote** (one per poll, DB-enforced) | any authenticated member | ✓ | ✓ | ✓ | ✓ | ✓ |
| Mailbox — **send** announcement / view sent | `settings:write` / `:read` | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Mailbox — inbox / mark read** | any authenticated member | ✓ | ✓ | ✓ | ✓ | ✓ |
| Mobile Manager — list devices / set config | `settings:read` / `:write` | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Mobile — register own device / read app config** | any authenticated member | ✓ | ✓ | ✓ | ✓ | ✓ |

- **Biometric integrity** (design-note-first, confirmed): dedup keys on the
  **device record id**, not the timestamp (a drifted re-push still dedups);
  device **clock skew is surfaced, not trusted**; unknown device/biometric-id
  punches **quarantine** (never dropped, no phantom student) and are
  **resolved → replayed** into exactly one attendance event. Proven in
  `test_platform.py`.
- † **`/biometric/ingest` on `settings:write` is a known pre-launch RELEASE
  BLOCKER** — it needs per-device token auth before real hardware connects
  (general admin session is too wide a door). Tracked in BUILD_PROGRESS.md.
