# Build Progress — Sidebar "Coming Soon" → Real Features

Tracks the full build-out of the 33 placeholder sidebar items into real,
permission-gated, tested features. Built in 7 phases (batches of related
features). Each feature kept its **Coming Soon** chip until its own page was
finished **and tested**, then was converted to a real routed item.

**Status legend:** `placeholder` (sidebar chip, no impl) · `in-progress` ·
`done+tested` (backend + frontend shipped, tests green, sidebar item live).

---

## 🏁 PROJECT COMPLETE — Closing Summary (all 7 batches `done+tested`)

**One clean statement of what's built and what's consciously left for the
pre-launch pass.**

### What shipped
- **33 / 33** placeholder features built end-to-end (model → schema → router/RBAC
  → frontend page with loading/error/empty → tests green), across **7 batches**.
- **0** "Coming Soon" placeholders remain — verified (`grep` clean across the
  frontend); the placeholder scaffolding itself was removed from the sidebar.
- **Backend test suite: 431 passed** (was 333 at the close of Batch 1; +98 across
  Batches 2–7). Frontend `tsc --noEmit`: **clean**.
- **Single linear migration head: `012_add_platform`** (003 → 012, each additive
  and reversible; no branches).
- Every destructive/financial operation proved its safety properties **in tests,
  per feature** — not assumed: atomicity, idempotency/double-apply guards,
  immutability (reverse-not-edit), who/when/before→after audit, and approval
  boundaries / segregation-of-duties (payroll approver ≠ creator; exeat approver
  ≠ requester; `payments:post` vs `payments:write` vs `wallet:spend`).

### Batch ledger
| Batch | Theme | Features | Migration |
|---|---|---|---|
| 1 | People & HR | 3 | 003 |
| 2 | Admissions & Enrollment | 4 | 004 (+005 safety) |
| 3 | Academic Records & Recognition | 4 | 006 |
| 4 | Pastoral, Boarding & Health | 4 | 007 |
| 5 | Finance & Accounting | 6 | 008, 009 |
| 6 | Operations & Student Finance | 6 | 010, 011 |
| 7 | Administration & Platform | 6 | 012 |
| | **Total** | **33** | head `012` |

### Consolidated deferral list — the pre-launch pass
Everything consciously left undone, in one place. Two are **launch gates**.

1. 🚨 **RELEASE BLOCKER — device-token auth for `POST /biometric/ingest`.**
   Ships gated on `settings:write` (sync worker = admin/service account). An
   attendance-ingest endpoint reachable with a general admin session is too wide a
   door for production hardware. Per-device tokens (issued on registration, scoped
   to ingest only, rotatable/revocable) **must close before any real ZKTeco device
   connects.**
2. 🚦 **Parent self-service wallet balance view** (deferred from Batch 6).
   Wallet/PocketMoney pages are staff-only; a parent funding a cashless wallet will
   immediately ask "how much is left?" Needs an **ownership-scoped** read
   (`payments:read` + `ParentGuardian` check; balance derivation already exists)
   surfaced on the parent dashboard / My Children. **Do before launch.**
3. 🧹 **Hospital/business dead-scaffolding removal** (post-build cleanup). These
   modules are dead in `SINGLE_SCHOOL_MODE` (routers unmounted; imported only for
   `Base.metadata`/tests) and exist purely to force model renames
   (`StudentMedicalRecord`, `SchoolPayslip`, `FinanceInvoice`). Dropping them
   removes the collisions and shrinks the surface. Deferred so the migration
   baseline isn't disturbed mid-build.
4. 🧹 **Clubs form EntityPicker retrofit** — the pre-existing Clubs form still uses
   raw text inputs for `advisor_id`/`student_id`; retrofit to `EntityPicker`
   (advisor → `staff`, member → `student`), as every Batch 1+ form already does.
5. 💡 **Tuckshop auto-draw** (product follow-up) — let a tuckshop/store sale draw
   directly from a student's wallet at the till (the `wallet:spend` capability +
   no-overdraw + period-lock already exist; this is the till-side wiring/UX).
6. 💡 **Cooperative loans / interest** (product follow-up) — the cooperative today
   models contributions + payouts (liability, derived balances). Member loans and
   interest accrual would post through the same ledger engine; not yet built.

> Resume rule (kept for reference): pick the first batch not fully `done+tested`
> — there are none — otherwise the project is complete; the next work is the
> pre-launch pass above.

---

## ✅ Logo + branding wired across portal and PDFs — done + verified live (2026-06-23)

> **Verified with the real assets in place.** The 10 binaries were generated from
> the single source `fairviewschool_logo.png` (Pillow) and dropped into
> `frontend/public/`; the dev server serves all 10 + the manifest at **HTTP 200**
> with correct content-types, and the favicon / header / splash / letterhead
> images were viewed and render correctly. Flipped to ✅.

The Fairview crest is wired into every surface the brief named. The integration
guide (`LOGO_INTEGRATION.md`) was written for a Vite/CRA app; this frontend is
**Next.js App Router**, so the intent was honoured with the correct Next
equivalents (no `index.html`; favicons/manifest via the `metadata`/`viewport`
API; assets served from `frontend/public/` with root-relative `/` URLs — the
guide's `/src/assets/` srcSet URLs would not resolve under Next).

- **Browser tab + PWA** — `app/layout.tsx` `metadata.icons` (`.ico` + 16/32 PNG +
  apple-touch) and `metadata.manifest`; `viewport.themeColor = #1d8a3a`. Manifest
  at `public/manifest.webmanifest` (icon-192 + icon-512), the PWA / Mobile-Manager
  install icon.
- **Header** — `components/branding/Brand.tsx` `<BrandMark>` replaces the generic
  `Building2` placeholder in `Sidebar.tsx`, height-matched (`h-8`) beside the name.
- **Loading / splash** — the crest replaces the placeholder in
  `components/loading/Splash.tsx` (keeps the pulse/ping); this is the loader the
  dashboard renders pre-mount. (Next renders server-side, so there is no blank
  "before React loads" SPA gap to fill — the Splash component is that surface.)
- **Documents / PDFs** — **there is no PDF-generation library in the project**
  (no reportlab/weasyprint server-side; no jspdf/react-pdf client-side). The real
  document-output path is **browser print → Save as PDF**. So the crest was wired
  into that path: a reusable `<PrintLetterhead>` + `@media print` rules in
  `globals.css` (`.no-print` hides sidebar/topbar/controls, `.print-only` reveals
  the letterhead). Wired into **all four document types** that people print/keep:
  **Report Cards** (existing Print), **Invoice Center** (per-row Print → branded
  invoice: billed-to, lines, total), **Payroll** (per-run Print → one branded
  **payslip** page per staff member, page-broken so each person keeps their own),
  and **Transcripts / Mark Books** (Print on the transcript detail → branded
  academic record). One reusable `<PrintLetterhead title=…>` across all four.
- **Theme colours** — left as-is on purpose. The app's `brand` palette is already
  green (`brand-600 = #16a34a`, ≈ the crest's `#1d8a3a`); regenerating the whole
  scale from the crest green would shift every shade across the app right before
  launch — not a "clean swap", so skipped per the brief's own caution.
- **Asset generation** — all 10 files were produced from the single source
  `fairviewschool_logo.png` (246×225) via Pillow at the exact names/sizes.
  `logo-transparent.png` clears **only the outer background** (silhouette built by
  morphological close → fill-holes → erode), keeping the crest's interior white
  field — no holes punched, confirmed on a magenta composite. Favicon frames are
  square (16/32/48/64). `apple-touch-icon` + `icon-192/512` are composited on
  **white** (iOS renders transparent apple-touch icons on black; matches the
  manifest `background_color`); favicons/navbar/square/master stay transparent.
- **Verification (live)** — `tsc --noEmit` **clean**; dev server (Next 15.1.3)
  compiles `/` and `/login` with no errors. All 10 assets + the manifest return
  **HTTP 200** with correct content-types (`image/x-icon`, `image/png`,
  `application/manifest+json`) and byte sizes matching the generated files. The
  rendered `<head>` emits `theme-color #1d8a3a`, the `manifest` link, and the
  `.ico`/32/16/apple-touch icon tags. The favicon (tab), header logo, splash crest
  (`logo-transparent`) and document letterhead (`logo-square`) were **fetched back
  from the server and viewed** — all render correctly. The drop-here note was
  removed from `public/`.
  > Honest limit: there's no headless browser here (no Playwright), so this is
  > "assets served + valid + correctly referenced + visually inspected", not a
  > screenshot of the running React header/splash/print dialog — but those surfaces
  > reference these exact verified URLs and the pages compile.

---

## Batch 1 — People & HR  ·  status: done+tested ✅

| Feature | Sidebar id | Page route | Permission | Status |
|---|---|---|---|---|
| Parents Directory | `parents` | `/dashboard/modules/school/parents` | `school:parents:read` / `:write` | done+tested |
| Staff Assessment | `staff-assessment` | `/dashboard/modules/school/staff-assessment` | `hr:write` | done+tested |
| Talent Pool | `talent-pool` | `/dashboard/modules/school/talent-pool` | `hr:write` | done+tested |

> Note: there are **33** placeholders total (an exact recount of the initial
> "~35" estimate). Batches 2–7 below remain as planned.

**Batch 1 deliverables**
- Backend: reused `ParentGuardian`; new `StaffAssessment` + `TalentCandidate`
  models (`app/models/hrm.py`); schemas `app/schemas/people.py` +
  `app/schemas/hr_development.py`; routers `app/routers/modules/parents.py`
  (`/school/parents`) + `app/routers/hr_development.py` (`/hr/assessments`,
  `/hr/talent`); registered in `app/main.py`.
- Migration: `alembic/versions/003_add_people_hr_development.py` (additive,
  reversible; single linear head).
- RBAC: `ROUTE_ACCESS` + Sidebar updated (lockstep). `school:parents:*` covered
  by the broad-grant hierarchy (staff-only); HR surfaces gated `hr:write`.
- Frontend: `parentsApi` + `hrDevApi` (`lib/api.ts`), `hooks/usePeople.ts`,
  types in `types/index.ts`, 3 pages with loading/error/empty states; the 3
  sidebar placeholders converted to real routed items.
- Tests: `tests/test_parents_directory.py` (11) + `tests/test_hr_development.py`
  (12) → 23 green. Full backend suite **333 passed**; frontend `tsc --noEmit` clean.

## Batch 2 — Admissions & Enrollment  ·  status: done+tested ✅

| Feature | Sidebar id | Page route | Permission | Status |
|---|---|---|---|---|
| Admissions & Enquiries | `admissions` | `/dashboard/modules/school/admissions` | `school:admissions:read` / `:write` (admit → `school:students:write`) | done+tested |
| Entrance Exams | `entrance-exams` | `/dashboard/modules/school/entrance-exams` | `school:admissions:read` / `:write` | done+tested |
| Promotion Manager | `promotion` | `/dashboard/modules/school/promotion` | `school:students:read` / `:write` | done+tested |
| Transfer Manager | `transfer` | `/dashboard/modules/school/transfer` | `school:students:read` / `:write` | done+tested |

**Batch 2 deliverables**
- Backend: `app/models/modules/admissions.py` (AdmissionApplication,
  EntranceExam, EntranceExamResult, PromotionRecord, TransferRecord); schemas
  `app/schemas/admissions.py`; one router `app/routers/modules/admissions.py`
  (prefix `/enrollment`) registered in `app/main.py`; models loaded at runtime
  (`database.py`) + in tests (`conftest.py`).
- Lifecycle bridges: `POST /enrollment/applications/{id}/admit` creates a
  Student from the application (idempotent, 409 on re-admit); promotions apply
  the roster effect (promoted → class change, graduated → deactivate, repeated →
  record only); completing a transfer deactivates the student.
- Migration: `alembic/versions/004_add_admissions_enrollment.py` (additive,
  reversible; single linear head).
- Frontend: `enrollmentApi` (`lib/api.ts`), `hooks/useEnrollment.ts`
  (+ `useClassOptions` / `useClassStudents`), types, 4 pages with loading/error/
  empty states; admissions/transfer forms use **EntityPicker**; the 4 sidebar
  placeholders converted to real routed items.
- Tests: `tests/test_enrollment.py` → 14 green. Frontend `tsc --noEmit` clean.

## Batch 3 — Academic Records & Recognition  ·  status: done+tested ✅

| Feature | Sidebar id | Page route | Permission | Status |
|---|---|---|---|---|
| Subject Selection | `subject-selection` | `/dashboard/modules/school/subject-selection` | `school:subjects:read` / `:write` | done+tested |
| Mark Books & Transcripts | `mark-books` | `/dashboard/modules/school/mark-books` | `school:grades:read` / `:write` | done+tested |
| Report Workflow | `report-workflow` | `/dashboard/modules/school/report-workflow` | `school:reports:write` | done+tested |
| Merit & Awards (typed: conduct_point \| academic_award; tabbed UI, one model) | `merits` | `/dashboard/modules/school/merits` | `school:behaviour:read` / `:write` | done+tested |

**Batch 3 deliverables**
- Backend: `app/models/modules/academics.py` (SubjectSelection, Transcript +
  TranscriptEntry, ReportApproval, Recognition); schemas `app/schemas/
  academics.py`; one router `app/routers/modules/academics.py` (prefix
  `/academics`); migration `006`; registered + loaded at runtime and in tests.
- **Merit & Awards** is ONE typed `Recognition` model (`conduct_point` |
  `academic_award`), shared backend, tabbed UI; conduct points feed a house
  leaderboard (`GET /academics/recognitions/leaderboard`).
- Transcripts auto-compute the average from entry scores (recomputed on
  add/remove entry); report workflow stamps the actor per stage + audits
  stage transitions.
- RBAC: report-workflow + merits use WRITE/read scopes that students/parents
  lack (they hold only `reports:read` for their own card), keeping the admin
  tools staff-only. `ROUTE_ACCESS` + Sidebar updated (academics ×3 + pastoral ×1).
- Frontend: `academicsApi`, `hooks/useAcademics.ts`, types, 4 pages with
  loading/error/empty states (student forms use **EntityPicker**).
- Tests: `tests/test_academics.py` → 11 green. Frontend `tsc --noEmit` clean.

## Batch 4 — Pastoral, Boarding & Health  ·  status: done+tested ✅

| Feature | Sidebar id | Page route | Permission | Status |
|---|---|---|---|---|
| Hostel / Boarding | `hostel` | `/dashboard/modules/school/hostel` | `school:hostel:read` / `:write` | done+tested |
| Exeat Requests | `exeat` | `/dashboard/modules/school/exeat` | `school:hostel:read/write`; **approve = `school_admin:write`** | done+tested |
| Mentor Reports | `mentor` | `/dashboard/modules/school/mentor` | `school:behaviour:read` / `:write` | done+tested |
| Medicals | `medicals` | `/dashboard/modules/school/medicals` | **`medical:read` / `:write`** (org_admin + nurse only) | done+tested |

**Batch 4 deliverables**
- **Medicals confidentiality**: NEW top-level `medical` namespace (registered in
  `workspace.py`, frontend `workspace.ts`) — deliberately OUTSIDE the `school:read`
  hierarchy so teachers/general staff CANNOT read health data. NEW `nurse` system
  role (`medical:read`+`medical:write`+`hr:read` only, no `school:*`); `medical:*`
  added to `org_admin`. Medical router uses `require_module("school")` (org gate)
  + `medical:*` checker so the nurse — who holds no school scope — still reaches it.
  Soft-delete + every entry/deletion audited (no clinical detail in the log).
- **Exeat approver + audit**: requesting needs `school:hostel:write` (teachers);
  **approving/rejecting needs `school_admin:write`** (org_admin/manager) — a
  teacher canNOT authorise a child leaving campus. Approver + decision time +
  note recorded and written to the immutable audit log; status transitions
  guarded (no double-approve; return only after approve).
- Backend: `app/models/modules/pastoral.py` (Hostel, BoardingAllocation,
  ExeatRequest, MentorReport, StudentMedicalRecord — renamed to avoid the
  retained hospital-EMR `MedicalRecord`); routers `pastoral.py` + `medical.py`;
  schemas `pastoral.py` + `medical.py`; migration `007`.
- Frontend: `pastoralApi`/`medicalApi`, `hooks/usePastoral.ts`, types, 4 pages
  (Exeat approve/reject buttons shown only to approvers; Medicals shows a
  confidentiality banner); 4 sidebar placeholders → real routes.
- Tests: `tests/test_medical.py` (7 — incl. teacher CANNOT read) +
  `tests/test_pastoral.py` (8 — incl. exeat approver gating + audit) → 15 green.
  Full backend **381 passed**; frontend `tsc --noEmit` clean.

> **New role note:** a `Nurse` system role is now seeded for every school org
> (`SCHOOL_ROLE_SLUGS`). Manager is intentionally NOT granted `medical` ("admin
> only" per request) — flip by adding `medical:read/write` to the manager preset.

## Batch 5 — Finance & Accounting  ·  status: done+tested ✅ (6 of 6)

| Feature | Sidebar id | Page route | Permission | Status |
|---|---|---|---|---|
| Chart of Accounts (+ Accounting Periods) | `accounts` | `/dashboard/modules/school/accounts` | view `payments:write` · lock `payments:post` | done+tested |
| Invoice Center | `invoices` | `/dashboard/modules/school/invoices` | view/draft `payments:write` · post/pay/void `payments:post` | done+tested |
| Payroll | `payroll` | `/dashboard/modules/school/payroll` | draft `payments:write` · approve `payments:post` (+approver≠creator) | done+tested |
| Petty Cash & Budget | `petty-cash` | `/dashboard/modules/school/petty-cash` | record `payments:post` · budgets `payments:write` | done+tested |
| Cash Transactions | `cash-txns` | `/dashboard/modules/school/cash-txns` | record/void `payments:post` | done+tested |
| Store & Inventory | `store` | `/dashboard/modules/school/store` | items/issue `payments:write` · purchase `payments:post` | done+tested |

**Batch 5 (first half) deliverables**
- **Ledger engine** (`app/services/ledger.py`) — the single enforcement layer.
  `post_journal_entry` rejects unbalanced/one-line/wrong-sided/unknown-account
  entries (422) and locked-period postings (409); writes header+lines atomically
  inside the request txn; audits every post. `reverse_entry` makes corrections
  immutable (mirror entry, original linked + flagged, no edits/deletes).
- Models `app/models/modules/finance.py` (LedgerAccount, AccountingPeriod,
  JournalEntry + JournalLine **with CHECK constraints**, Invoice + InvoiceLine,
  PayrollRun + **SchoolPayslip** — renamed to avoid the business `Payslip`).
  Money is `Numeric(14,2)`; `Decimal` end to end.
- **Accounting periods** reserved in migration `008` with `journal_entries.period_id`
  + a lock guard that blocks (back-)posting into a closed period.
- **SoD / two-person**: new `payments:post` scope + new **`accountant`** role
  (`payments:read/write/post`, finance-only, no `school:*`). Manager drafts but
  cannot post. Payroll approval enforces `approved_by != created_by` in code.
- Router `app/routers/modules/finance.py` (prefix `/finance`, `require_module`
  + payments checks); `financeApi`, `hooks/useFinance.ts`, types, 3 pages
  (accounts+periods, invoices, payroll); 3 of 6 sidebar placeholders → real.
- Tests: `test_finance_ledger.py` (10 — double-entry, period-lock, reverse,
  atomicity, RBAC) + `test_finance_features.py` (6 — invoice lifecycle/immutable,
  payroll two-person) → 16 green.

**Batch 5 (second half) deliverables**
- `app/routers/modules/finance_ops.py` + `app/schemas/finance_ops.py` +
  models (Budget, PettyCashTxn, CashTransaction, StoreItem, StockMovement);
  migration `009`. Every money movement posts through the SAME ledger engine.
- **Petty Cash** (Dr Expense / Cr Petty-Cash) with a **soft over-budget warning**
  (records reality, never blocks). **Cash Transactions** (receipt Dr Cash/Cr
  counter; payment Dr counter/Cr Cash). **Store** items + **purchase-side** posting
  (Dr Inventory / Cr funding; no COGS-on-sale) + non-financial issue/adjust.
- 3 pages (petty-cash, cash-txns, store) + final 3 sidebar placeholders → real.
- Tests: `test_finance_ops.py` (12) **explicitly prove per-feature guard
  inheritance** — petty-cash & cash into a locked period → 409, the store posting
  path rejects an unbalanced entry → 422, every feature posts a balanced entry,
  plus the soft budget warning + stock maths + RBAC.

### Model-rename collisions (Batches 4–5) + dead-scaffolding note
New school models/types collided with the **retained hospital/business modules**
and were renamed: `StudentMedicalRecord` (vs hospital `MedicalRecord`),
`SchoolPayslip` (vs business `Payslip`), `FinanceInvoice` (frontend type, vs
hospital/business `Invoice`). Backend dodges others by distinct table names
(`student_medical_records`, `school_payslips`, `store_items`, `cash_transactions`).

> **Cleanup candidate (after the build):** the hospital + business modules are
> **dead scaffolding in production** — `SINGLE_SCHOOL_MODE` defaults `True`, so
> their routers are NOT mounted (`main.py`); they're only imported for
> `Base.metadata`/tests and exist purely to force these renames. Dropping
> `app/models/modules/{hospital,business}.py` + `app/routers/modules/{hospital,
> business}.py` (and their `init_db`/`conftest` imports) would remove the
> collisions and shrink the surface. Deferred to a post-build cleanup pass so we
> don't disturb the migration baseline mid-build.

## Batch 6 — Operations & Student Finance  ·  status: done+tested ✅ (6 of 6)

| Feature | Sidebar id | Page route | Permission | Status |
|---|---|---|---|---|
| Wallet Manager | `wallet` | `/dashboard/modules/school/wallet` | view/admin `payments:write` · top-up/withdraw `payments:post` | done+tested |
| PocketMoney | `pocketmoney` | `/dashboard/modules/school/pocketmoney` | spend `wallet:spend` · limits `payments:write` | done+tested |
| Cooperative | `cooperative` | `/dashboard/modules/school/cooperative` | view/admin `payments:write` · contribute/payout `payments:post` | done+tested |
| Calendar & Planner | `calendar` | `/dashboard/modules/school/calendar` | `school:read` / `:write` | done+tested |
| Facility Management | `facility` | `/dashboard/modules/school/facility` | `school_admin:read` / `:write` | done+tested |
| Visitor Management | `visitor` | `/dashboard/modules/school/visitor` | `school_admin:read` / `:write` | done+tested |

**Batch 6 (money half) deliverables**
- **Ledger-backed student money** — `app/models/modules/wallet.py` (StudentWallet,
  WalletEntry, CooperativeMember, CoopEntry) + `app/routers/modules/wallet.py` +
  `app/schemas/wallet.py`; migration `010`. Every move posts through the shared
  ledger engine; **balances are DERIVED** (Σ subledger over non-reversed entries),
  never stored.
- **Liability accounting** (per your direction): Wallet Float (2200) + Cooperative
  Fund (2300) are **liability** control accounts (auto-ensured in the CoA). Top-up
  = Dr Cash / Cr Float; **income recognised only on spend** (Dr Float / Cr Income);
  cooperative contributions = Dr Cash / Cr Fund (held on behalf, not revenue).
- **PocketMoney = the same wallet** + a per-student daily spend limit; no second pot.
- **Dedicated `wallet:spend` scope** (new namespace) — till staff can ONLY draw a
  student's own wallet down to income (no-overdraw + period-locked); cannot move
  cash, post invoices/payroll, or create arbitrary entries. Granted to staff (till)
  + manager/accountant/admin. Top-up/withdraw/cooperative cash-in/out stay on
  `payments:post`. Reconciliation endpoints tie GL ↔ derived subledger.
- 3 pages + access map + 3 of 6 sidebar placeholders → real.
- Tests: `tests/test_wallet.py` (8) — wallet:spend constrained (CAN spend, CANNOT
  top-up/withdraw/post), no-overdraw HARD block, **GL↔subledger reconciliation
  ties out**, period-lock inherited, daily limit, cooperative liability.

**Batch 6 (non-financial half) deliverables**
- `app/models/modules/operations.py` (CalendarEvent, Facility, FacilityBooking,
  VisitorLog, StudentCollection) + `app/routers/modules/operations.py` (prefix
  `/operations`) + `app/schemas/operations.py`; migration `011`.
- **Calendar & Planner** (school:read/write). **Facility Management** (school_admin)
  with a **double-booking guard** (overlapping active booking → 409). **Visitor
  Management** as a **safeguarding record** (school_admin): sign-in/out + child
  collection are **audit-logged**, **soft-deleted only** (never silently removed),
  and a collection **requires + captures the authorising staff member**.
- 3 pages (calendar, facility, visitor w/ Visitors + Child-Collection tabs) +
  access map + final 3 sidebar placeholders → real.
- Tests: `tests/test_operations.py` (7) — calendar CRUD, facility double-booking
  conflict, visitor audit + soft-delete-not-silent, collection authoriser captured
  + audited + soft-delete, RBAC (calendar=school; facility/visitor=school_admin).

## Batch 7 — Administration & Platform  ·  status: done+tested ✅ (6 of 6) — FINAL

| Feature | Sidebar id | Page route | Permission | Status |
|---|---|---|---|---|
| School Setup (sessions/terms, houses, grading bands) | `school-setup` | `/dashboard/modules/school/school-setup` | `settings:read` / `:write` | done+tested |
| Biometric Devices (ZKTeco → attendance events) | `biometric` | `/dashboard/modules/school/biometric` | `settings:read` / `:write` | done+tested |
| Custom Fields (EAV per entity type) | `custom-fields` | `/dashboard/modules/school/custom-fields` | `settings:read` / `:write` | done+tested |
| Voting System (polls, one-vote, derived results) | `voting` | `/dashboard/modules/school/voting` | `settings:read` / `:write` (vote = any member) | done+tested |
| Mailbox (announcements, read receipts) | `mailbox` | `/dashboard/modules/school/mailbox` | send `settings:write` · inbox = any member | done+tested |
| Mobile Manager (device/token registry + app config) | `mobile` | `/dashboard/modules/school/mobile` | `settings:read` / `:write` (register = any member) | done+tested |

**Batch 7 deliverables**
- Backend: `app/models/modules/platform.py` (15 models) + `app/schemas/platform.py`;
  two routers — `app/routers/modules/biometric.py` (prefix `/biometric`) and
  `app/routers/modules/platform.py` (prefix `/platform`); migration `012`;
  registered + loaded at runtime and in tests. All admin surfaces gated
  `settings:*` (org_admin only — manager/teacher/staff/student/parent lack it).
- **Biometric → existing attendance layer** (design-note-first, confirmed): a
  `BiometricDevice` registry + `BiometricEnrollment` (biometric id → student) map.
  `POST /biometric/ingest` resolves each punch and feeds the EXISTING
  `attendance_service.ingest` (so dedup, daily-record derivation, parent
  notifications and audit all reuse the proven path).
  - **Idempotency keys on the DEVICE RECORD ID** (`external_ref`), NOT the
    timestamp: a buffered re-push — even after a clock-drift correction — ingests
    once (`uq_attendance_event_source_ref`). A deterministic synthetic ref is used
    only when a device exposes no record id.
  - **Authoritative clock = the device punch time** for `event_time`; the server
    stamps receipt and **surfaces `clock_skew_seconds`** on the device (visible in
    the UI, never trusted to mint a punch).
  - **Unmapped punches QUARANTINE** (`UnmappedPunch`): a punch from an unknown
    device or biometric id is never dropped and never auto-creates a student — it
    lands in a "Needs review" queue and is **resolved → replayed** into a real
    attendance event (and optionally enrolled) or explicitly discarded (audited).
- **Voting integrity**: one vote per `(poll, voter)` is **DB-enforced**
  (`uq_poll_votes_one_per_voter` → second vote is a hard 409); results are
  **derived** from the votes, never a mutable tally; closed polls reject votes.
- **Mailbox** = announcements (admin → recipients / all-staff) with read receipts,
  **NOT** real-time chat (that's Messenger). **Mobile Manager** = a device/push-token
  registry + key/value app-config toggles, **NOT** an app build system.
- Frontend: `biometricApi` + `platformApi` (`lib/api.ts`), `hooks/usePlatform.ts`,
  types, **6 pages** (biometric w/ Devices·Enrollments·Needs-review tabs;
  school-setup w/ Sessions·Houses·Bands; custom-fields; voting w/ live result
  bars; mailbox w/ Inbox·Compose·Sent; mobile w/ Devices·Config) — all with
  loading/error/empty states. The **final 6** sidebar placeholders → real routes.
- Tests: `tests/test_platform.py` (7) — biometric dedup-on-record-id (drifted
  re-push still dedups), clock-skew surfaced, unknown-device/id quarantine,
  resolve→replay = exactly one event, voting one-vote + derived results, mailbox
  send/inbox/read, and RBAC (settings:* admin-only).

### Dead-scaffolding cleanup done in this batch
With all 33 placeholders now real, the `soon()` helper, the `comingSoon` NavItem
field + render branch, and the "Soon" badge were **removed from
`components/layout/Sidebar.tsx`**. No "Coming Soon" string remains anywhere in the
frontend; every sidebar item is a real, permission-gated route.

---

### Safety hardening — destructive roster mutations (promotion / graduation / transfer)
Confirmed/added the four required safety properties (migration `005`):
- **Atomicity** — *was partial* (request-scoped txn via `get_db`). **Hardened**:
  bulk promotion now validates ALL students before mutating any, so a bad/
  ineligible id rejects the whole run with nothing half-applied.
- **Idempotency** — *was missing* for promotion/transfer (admit already guarded).
  **Added**: promotion refuses inactive (graduated/transferred) students;
  transfer blocks a second transfer of a departed student and only deactivates
  on the *transition* into completed (re-completing is a no-op).
- **Audit (who/when/before→after)** — *domain tables already captured it*;
  **added** immutable per-student `AuditLog` rows with `old_values`/`new_values`
  (class_id, is_active) on every promotion + transfer completion + revert.
- **Preview & reversibility** — *both missing*. **Added** `POST /enrollment/
  promotions/preview` (dry-run: eligible vs skipped, no writes) and run grouping
  via `batch_id` + `POST /enrollment/promotions/{batch_id}/revert` (restores
  pre-run class/active state from a snapshot; idempotent). Frontend: promotion is
  now preview-then-confirm with an "Undo last run" control.
- Tests: 8 added to `test_enrollment.py` (22 total). Full backend **355 passed**.

### Shared infrastructure
- **EntityPicker** (`frontend/components/inputs/EntityPicker.tsx`) — reusable
  type-ahead that searches people by name and returns the id. Types:
  `student` (→ `GET /school/students?search=`), `parent` / `staff`
  (→ `GET /messenger/contacts?search=`, auth-only). No new search endpoints
  were added. Batch 1 parents + staff-assessment forms retrofitted to use it;
  Batch 2 onward uses it natively. Raw-id entry is gone from new forms.

### Follow-ups (cleanup, not blocking)
- [ ] **Clubs form** still uses raw text inputs for advisor_id / student_id
  (`.../modules/school/clubs/page.tsx`). Retrofit to `EntityPicker`
  (advisor → `staff`, member → `student`). Left as-is for now per request.
- [ ] **Parent self-service wallet balance view** (deferred from Batch 6).
  Wallet/PocketMoney pages are staff-only (`payments:write` / `wallet:spend`).
  Parents funding a cashless wallet will immediately ask "how much is left?" —
  add an **ownership-scoped** read so a parent sees ONLY their own child's
  balance + recent entries. Backend balance derivation already exists
  (`_wallet_balance`); needs a parent-facing endpoint gated `payments:read` +
  per-child ownership check (reuse the `ParentGuardian` link), and a small
  surface on the parent dashboard / My Children. **Do before launch.**
- [ ] **Hospital/business dead-scaffolding removal** — see the dead-scaffolding
  note below; post-build cleanup once the migration baseline is stable.
- [ ] 🚨 **RELEASE BLOCKER — device-token auth for `POST /biometric/ingest`.**
  Ships gated on `settings:write` (sync worker = admin/service account). An
  attendance-ingest endpoint reachable with a general admin session is too wide a
  door for production hardware. **Must close before any real ZKTeco device
  connects:** per-device tokens (issued on device registration), scoped to ingest
  only, rotatable/revocable. Not a nice-to-have — a launch gate.

### Decisions / clarifications carried forward
- **Merit & Awards** (Batch 3): ONE recognition model with a `type` field
  (`conduct_point` | `academic_award`). Conduct points = teacher awards/deducts,
  house-based, leaderboard. Academic awards = honor roll / prizes / certificates,
  periodic. Surfaced as two tabs on one page sharing the same backend.
- **Biometric Devices** (Batch 7): ZKTeco attendance hardware wired into the
  existing attendance event layer (clock in/out → attendance records). NOT staff
  login/identity.
- RBAC: visibility is permission-driven. The 3-part scope hierarchy in
  `User.has_permission` means a teacher's broad `school:read`/`school:write`
  auto-covers any new `school:<feature>:*` scope, while students/parents (narrow
  scopes only) stay out — so most batches need no preset change, only
  `lib/access.ts` + `ROUTE_ACCESS` entries (Sidebar + RouteGuard in lockstep).
