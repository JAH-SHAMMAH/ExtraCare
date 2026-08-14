// Centralised route → permission map (Phase 7 RBAC).
//
// Single source of truth consumed by BOTH:
//   • Sidebar      — hides a nav item when the user lacks its permission.
//   • RouteGuard   — blocks direct-URL access to a page the user can't see.
//
// Keeping one table means the sidebar and the URL guard can never drift apart:
// if a link is hidden, navigating to it directly is denied too. Matching is by
// longest prefix, so deeper routes (…/attendance/dashboard) can require a
// stricter scope than their parent (…/attendance).
//
// Personal "my-" pages (/dashboard/my-children, /my-timetable, /my-classes …)
// are intentionally ABSENT — they carry no module permission; their data is
// resolved + ownership-scoped server-side from the caller's identity, and the
// sidebar shows them by active view-role instead.

export interface RouteAccess {
  prefix: string;
  permission: string;      // primary permission (shown as "Required:" on the block panel)
  // Optional: a route reachable by ANY ONE of several permissions. When set, the
  // user may view the page if they hold `permission` OR any entry in `anyOf`.
  // Mirrors a backend `AnyPermissionChecker` so the sidebar/guard don't hide a
  // page the API would actually let the user use (e.g. a cashier collecting a
  // store pickup: page reachable by `store:sell` OR `payments:write`).
  anyOf?: string[];
}

export const ROUTE_ACCESS: RouteAccess[] = [
  // ── Core / platform ────────────────────────────────────────────────
  { prefix: "/dashboard/analytics", permission: "analytics:read" },
  { prefix: "/dashboard/users", permission: "users:write" },
  { prefix: "/dashboard/audit", permission: "audit_logs:read" },
  { prefix: "/dashboard/settings", permission: "settings:read" },
  { prefix: "/dashboard/billing", permission: "settings:read" },
  // HR — self-service vs admin. Order doesn't matter (longest-prefix wins).
  { prefix: "/dashboard/hrm/my-info", permission: "hr:read" },
  { prefix: "/dashboard/hrm/leave/admin", permission: "hr:write" },
  // Leave completion: Configure + Assign are admin (hr:write); Entitlements is
  // self-service (inherits hr:read from /leave below). Longest-prefix wins.
  { prefix: "/dashboard/hrm/leave/configure", permission: "hr:write" },
  { prefix: "/dashboard/hrm/leave/assign", permission: "hr:write" },
  { prefix: "/dashboard/hrm/leave", permission: "hr:read" },
  // Phase 4: Recruitment + Disciplinary — confidential HR admin (hr:write).
  { prefix: "/dashboard/hrm/recruitment", permission: "hr:write" },
  // Self-service: a staff member's OWN disciplinary record (longest-prefix wins,
  // so this hr:read route sits under the hr:write disciplinary parent).
  { prefix: "/dashboard/hrm/disciplinary/my-actions", permission: "hr:read" },
  { prefix: "/dashboard/hrm/disciplinary", permission: "hr:write" },
  // Phase 4 Batch 2: Performance (hr:write); Roles & Permissions = role mgmt (roles:write).
  // ("Access Control" now names the staff-attendance feature below, not this page.)
  { prefix: "/dashboard/hrm/performance", permission: "hr:write" },
  { prefix: "/dashboard/hrm/training", permission: "hr:write" },
  { prefix: "/dashboard/hrm/roles", permission: "roles:write" },
  // Phase 2 Access Control: staff attendance. Admin clock log (hr:write) + a
  // self-service "My Attendance" (hr:read) — longest-prefix keeps the staff route
  // reachable under the hr:write parent.
  { prefix: "/dashboard/hrm/attendance/my", permission: "hr:read" },
  { prefix: "/dashboard/hrm/attendance", permission: "hr:write" },
  { prefix: "/dashboard/hrm", permission: "hr:write" },

  // ── School module (fine-grained per feature) ───────────────────────
  // The Students MODULE (roster admin: withdrawal, inactive, pickup) is an
  // admin surface — the classroom tier keeps `school:students:read` for its
  // pupils' records (marking, attendance, pastoral) but has no Students nav.
  { prefix: "/dashboard/modules/school/students", permission: "school_admin:read" },
  // Teachers module is Admin/Super-User-only (settings:read) — covers View
  // Teachers + Assign To School. (The shared /school/teachers API stays
  // school:read for Lesson Planner / Ratings.)
  { prefix: "/dashboard/modules/school/teachers", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/staff", permission: "school_admin:read" },
  // Class + YearGroup MANAGEMENT is admin taxonomy. The classroom tier keeps
  // `school:classes:read` so its class pickers resolve, but gets no nav item.
  { prefix: "/dashboard/modules/school/classes", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/subjects", permission: "school:subjects:read" },
  // Insights dashboard is admin-only; the marking page needs write.
  { prefix: "/dashboard/modules/school/attendance/dashboard", permission: "school_admin:read" },
  // Live monitor is a staff read view over the check-in/out events.
  { prefix: "/dashboard/modules/school/attendance/monitor", permission: "school:attendance:read" },
  // Attendance Setup edits org-wide config (late cutoff + reason codes) — admin-only.
  { prefix: "/dashboard/modules/school/attendance/setup", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/attendance", permission: "school:attendance:write" },
  { prefix: "/dashboard/modules/school/exams", permission: "school:exams:read" },
  { prefix: "/dashboard/modules/school/grades", permission: "school:grades:read" },
  // TimeTable: STRUCTURE editing (setup, periods, activities, schedules, the
  // Time Tabler, curriculum, subject attendance) is admin — it requires the
  // write scope, which the classroom tier does not hold. Viewing rides
  // `school:timetable:read`, which it does.
  { prefix: "/dashboard/modules/school/timetable/setup", permission: "school:timetable:write" },
  { prefix: "/dashboard/modules/school/timetable/periods", permission: "school:timetable:write" },
  { prefix: "/dashboard/modules/school/timetable/activities", permission: "school:timetable:write" },
  { prefix: "/dashboard/modules/school/timetable/schedules", permission: "school:timetable:write" },
  { prefix: "/dashboard/modules/school/timetable/tabler", permission: "school:timetable:write" },
  { prefix: "/dashboard/modules/school/timetable/curriculum", permission: "school:timetable:write" },
  { prefix: "/dashboard/modules/school/timetable/subject-attendance", permission: "school:timetable:write" },
  { prefix: "/dashboard/modules/school/timetable", permission: "school:timetable:read" },
  // Lesson Planner: authoring is the teacher's; Setup (categories/weeks/settings/
  // supervisors/clone/schedules) and the Approve queue are supervisor/admin.
  { prefix: "/dashboard/modules/school/lessons/setup", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/lessons/approve", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/lessons", permission: "school:lessons:write" },
  // Library browse + own loans: students see sidebar My Library quick-link, NOT the admin section.
  // The admin "Dashboard" itself is school:write (old parent), and all children require write.
  // Longest-prefix match ensures specific children block before the parent.
  { prefix: "/dashboard/modules/school/library/catalogue", permission: "school:library:write" },
  { prefix: "/dashboard/modules/school/library/loans", permission: "school:library:write" },
  { prefix: "/dashboard/modules/school/library/users", permission: "school:library:write" },
  { prefix: "/dashboard/modules/school/library/setup", permission: "school:library:write" },
  { prefix: "/dashboard/modules/school/library/reviews", permission: "school:library:write" },
  { prefix: "/dashboard/modules/school/library", permission: "school:library:write" },
  { prefix: "/dashboard/modules/school/sms", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/transport", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/report-cards", permission: "school:reports:read" },
  { prefix: "/dashboard/modules/school/fees", permission: "payments:read" },
  { prefix: "/dashboard/modules/school/ratings", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/eclassroom", permission: "school:classroom:read" },
  // eClassroom (virtual classroom) — admin module, coarse school:write (excludes
  // students, who hold only school:classroom:*). Matches the router gate.
  // "Manage eClassrooms" is the teacher's own virtual classrooms (the schedules
  // cluster, gated school:classroom:write server-side); Setup / Programs /
  // Broadcast stay admin. Longest-prefix wins.
  // eClassroom admin configuration (setup, programs, broadcast) — admin-only.
  // Teacher's own classroom management (manage) uses school:classroom:manage.
  { prefix: "/dashboard/modules/eclassroom/setup", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/eclassroom/programs", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/eclassroom/broadcast", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/eclassroom/manage", permission: "school:classroom:manage" },
  { prefix: "/dashboard/modules/eclassroom", permission: "school:write" },
  // Voting System — admin children school:write; My Votes is voter-facing so
  // eligible students (school:classroom:read) can reach it. Longest-prefix wins.
  { prefix: "/dashboard/modules/voting/my-votes", permission: "school:classroom:read" },
  { prefix: "/dashboard/modules/voting", permission: "school:write" },
  // Question Bank holds correct answers — staff-only, on the dedicated
  // `school:cbt:manage` scope (teachers + exam officers hold it; students hold
  // only the cbt scope that sits tests). Longer prefix wins over /cbt above.
  { prefix: "/dashboard/modules/school/cbt/question-bank", permission: "school:cbt:manage" },
  // Result Manager exposes every student's scores + correct answers — staff-only.
  { prefix: "/dashboard/modules/school/cbt/results", permission: "school:cbt:manage" },
  // Interventions surface flagged students' scores; Setup edits org-wide defaults — admin-only.
  // The backend gates allow access via school:read OR school:cbt:manage, but the test/nav
  // intentionally restrict these to admins only (teachers see Question Bank + Results but not
  // these admin operations). Backend FIX: split these to use a strict gate (school:read only,
  // no AnyPermissionChecker with school:cbt:manage).
  { prefix: "/dashboard/modules/school/cbt/interventions", permission: "school:read" },
  { prefix: "/dashboard/modules/school/cbt/settings", permission: "school:read" },
  // Admin CBT ops (import / export / reset / remark) — admin-only.
  // Same backend gate issue as above: currently allow school:read OR school:cbt:manage,
  // but should be school:read only.
  { prefix: "/dashboard/modules/school/cbt/import", permission: "school:read" },
  { prefix: "/dashboard/modules/school/cbt/export", permission: "school:read" },
  { prefix: "/dashboard/modules/school/cbt/reset", permission: "school:read" },
  { prefix: "/dashboard/modules/school/cbt/remark", permission: "school:read" },
  // Live Classes — staff only (teachers, exam officers). Currently MISSING from this
  // table; defining here to prevent inheritance from the parent /cbt route.
  { prefix: "/dashboard/modules/school/cbt/live", permission: "school:cbt:manage" },
  // CBT admin tree (Manage CBT, Question Bank, Results, etc.) — teachers/admins only.
  // Students access exams via the dedicated /dashboard/my-exams route instead.
  { prefix: "/dashboard/modules/school/cbt", permission: "school:cbt:read" },
  // Behaviour Tracker TAXONOMY (categories / sub-categories / levels / settings)
  // defines the school's scheme — admin config. Logging a record stays on
  // school:behaviour:* so teachers can record conduct. Longest-prefix wins.
  { prefix: "/dashboard/modules/school/behaviour/categories", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/behaviour/subcategories", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/behaviour/levels", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/behaviour/settings", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/behaviour", permission: "school:behaviour:read" },
  // Feedback section: Form / My Feedback inherit feedback:read (self-service);
  // Settings / Manager require feedback:write; Daily/Student-Daily/CRM are staff
  // surfaces on the broad school scopes. Longest-prefix match wins.
  // Feedback SETTINGS is org-wide config — admin tier, like every other Setup page.
  { prefix: "/dashboard/modules/school/feedback/settings", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/feedback/manage", permission: "school:feedback:write" },
  // Daily reports are AUTHORED by teachers — they ride the feedback scope (the
  // classroom tier holds it), matching the re-gated endpoints.
  { prefix: "/dashboard/modules/school/feedback/daily-reports", permission: "school:feedback:write" },
  { prefix: "/dashboard/modules/school/feedback/student-daily-reports", permission: "school:feedback:write" },
  // CRM is a view over Admissions data — gate it on the admissions scope.
  { prefix: "/dashboard/modules/school/feedback/crm", permission: "school:admissions:read" },
  { prefix: "/dashboard/modules/school/feedback", permission: "school:feedback:read" },
  // Club Enrollment is the teacher-facing action; Manage Clubs / Membership /
  // Assessment are club administration. Longest-prefix wins.
  { prefix: "/dashboard/modules/school/clubs/enrollment", permission: "school:clubs:write" },
  { prefix: "/dashboard/modules/school/clubs", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/journals", permission: "school:journals:read" },
  { prefix: "/dashboard/modules/school/remarks", permission: "school:journals:write" },
  { prefix: "/dashboard/modules/school/tuckshop", permission: "school_admin:read" },

  // ── Batch 1: People & HR ───────────────────────────────────────────────
  // Parents Directory: guardian PII → staff-only. `school:parents:read` is
  // covered for trusted roles by the broad-grant hierarchy; students/parents
  // (narrow scopes) never hold it, so the link hides + the URL is blocked.
  { prefix: "/dashboard/modules/school/parents", permission: "school:parents:read" },
  // Staff Assessment + Talent Pool: confidential HR admin → require hr:write
  // (org_admin + manager). Teachers hold only hr:read, so they're excluded.
  { prefix: "/dashboard/modules/school/staff-assessment", permission: "hr:write" },
  { prefix: "/dashboard/modules/school/talent-pool", permission: "hr:write" },

  // ── Batch 2: Admissions & Enrollment ───────────────────────────────────
  // Admissions + entrance exams sit on the admissions scope; promotion +
  // transfer mutate the roster so they require school:students:write.
  { prefix: "/dashboard/modules/school/admissions", permission: "school:admissions:read" },
  { prefix: "/dashboard/modules/school/entrance-exams", permission: "school:admissions:read" },
  { prefix: "/dashboard/modules/school/promotion", permission: "school:students:write" },
  { prefix: "/dashboard/modules/school/transfer", permission: "school:students:write" },

  // ── Batch 3: Academic Records & Recognition ────────────────────────────
  // report-workflow + merits require WRITE-tier scopes on purpose: students/
  // parents hold reports:read (own card) but not these, so the admin tools
  // stay staff-only. subject-selection/mark-books use subjects/grades read.
  { prefix: "/dashboard/modules/school/subject-selection", permission: "school:subjects:read" },
  { prefix: "/dashboard/modules/school/mark-books", permission: "school:grades:read" },
  // Approve/Process is an ADMIN action — school_admin (teachers hold school:write
  // => reports:write but NOT school_admin, so they're excluded). Matches the
  // re-gated report-workflow API (school_admin:write).
  { prefix: "/dashboard/modules/school/report-workflow", permission: "school_admin:read" },
  // Report Entry = the ADMIN score-entry desk (any class/subject). Teachers use
  // Make Report (their own timetable subjects) instead.
  { prefix: "/dashboard/modules/school/report-entry", permission: "school_admin:read" },
  // Make Report = the TEACHER score-entry page — scoped server-side to the
  // teacher's Timetable (class, subject) assignments.
  { prefix: "/dashboard/modules/school/make-report", permission: "school:reports:write" },
  // Reports View (broadsheet etc.) — class results view, admin/teacher only (gated on
  // school:reports:write). The API further class-teacher-gates it (a non-class-teacher
  // is blocked for that class). Students see their own report via /report-cards instead.
  { prefix: "/dashboard/modules/school/reports-view", permission: "school:reports:write" },
  // Reports Upload = ADMIN bulk import — school_admin only.
  { prefix: "/dashboard/modules/school/reports-upload", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/merits", permission: "school:behaviour:read" },

  // ── Batch 4: Pastoral, Boarding & Health ───────────────────────────────
  // Hostel + Exeat ride school:hostel; Mentor reports ride school:behaviour.
  // Medicals is CONFIDENTIAL: gated by the dedicated `medical` namespace, which
  // the broad school:read hierarchy does NOT reach — only org_admin + nurse.
  // A form/pastoral teacher's OWN-GROUP surfaces ride the non-boarding
  // `school:pastoral:read` slice; Pastoral Setup (org-wide config) and the whole
  // boarding cluster stay on school:hostel:read, which the classroom tier lacks.
  { prefix: "/dashboard/modules/school/pastoral-dashboard", permission: "school:pastoral:read" },
  { prefix: "/dashboard/modules/school/pastoral-report", permission: "school:pastoral:read" },
  { prefix: "/dashboard/modules/school/pastoral-students", permission: "school:pastoral:read" },
  { prefix: "/dashboard/modules/school/pastoral-setup", permission: "school:hostel:read" },
  // Point Entry + Points Analysis ride the Recognition ledger → school:behaviour.
  { prefix: "/dashboard/modules/school/point-entry", permission: "school:behaviour:read" },
  { prefix: "/dashboard/modules/school/points-analysis", permission: "school:behaviour:read" },
  { prefix: "/dashboard/modules/school/hostel-students", permission: "school:hostel:read" },
  { prefix: "/dashboard/modules/school/hostel-life", permission: "school:hostel:read" },
  { prefix: "/dashboard/modules/school/hostel-reports", permission: "school:hostel:read" },
  { prefix: "/dashboard/modules/school/hostel", permission: "school:hostel:read" },
  { prefix: "/dashboard/modules/school/exeat", permission: "school:hostel:read" },
  // Mentor Reports is a pastoral-management review surface (not in a teacher's nav).
  { prefix: "/dashboard/modules/school/mentor", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/behaviour-sanction", permission: "school:behaviour:read" },
  { prefix: "/dashboard/modules/school/medicals", permission: "medical:read" },

  // ── Batch 5: Finance & Accounting ──────────────────────────────────────
  // SENSITIVE back-office finance (Bank Ledger, Payroll) → the dedicated
  // `finance_admin:read` scope: Super User / Accountant / Head of Administration
  // ONLY. Deliberately NOT payments:* — org_admin/manager/cashier hold payments
  // for fee collection but must not reach the ledger or payroll. Fee-collection
  // surfaces (invoices) + treasury (petty-cash/cash — kept operational by
  // decision) stay on payments:write.
  { prefix: "/dashboard/modules/school/accounts", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/invoices", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/payroll", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/petty-cash", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/cash-txns", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/store", permission: "payments:write" },

  // ── Batch 6: Wallet / PocketMoney + Cooperative ────────────────────────
  // Wallet Manager + Cooperative are admin money surfaces → payments:write
  // (parents who hold payments:read for fees don't see them). PocketMoney is the
  // spend surface → the dedicated wallet:spend scope (till staff + finance roles).
  { prefix: "/dashboard/modules/school/wallet", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/pocketmoney", permission: "wallet:spend" },
  // Managing the item catalogue is an admin action (create/price items).
  { prefix: "/dashboard/modules/school/pocketmoney/items", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/cooperative", permission: "payments:write" },

  // ── Batch 6 non-financial ──────────────────────────────────────────────
  // Calendar rides school:read; Facility + Visitor (safeguarding) are admin-tier.
  { prefix: "/dashboard/modules/school/calendar", permission: "school:calendar:read" },
  // Facility Management: its own fine-grained scope so the dedicated `facilities`
  // role reaches it (org_admin + manager inherit via broad school_admin:read).
  { prefix: "/dashboard/modules/school/facility", permission: "school_admin:facility:read" },
  { prefix: "/dashboard/modules/school/visitor", permission: "school_admin:read" },

  // ── Batch 7: Administration & Platform (settings:* — admin only) ────────
  { prefix: "/dashboard/modules/school/school-setup", permission: "settings:read" },
  // Report Setup hub (Educare parity) — admin config, same tier as school-setup.
  { prefix: "/dashboard/modules/school/report-setup", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/biometric", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/custom-fields", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/voting", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/mailbox", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/mobile", permission: "settings:read" },

  // ── Educare parity — Finance additions (over the existing ledger) ───────
  // Ledger-backed surfaces (journal posts, statements, Broad View) → the
  // SENSITIVE finance_admin:read scope, not payments:*.
  { prefix: "/dashboard/modules/school/direct-posts", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/direct-transfer", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/financial-statements", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/finance-overview", permission: "finance_admin:read" },
  // Gateway API secrets are org_admin-only, on the SEPARATE payment_gateways
  // namespace (NOT payments:*, which accountants/managers hold). See finance.py.
  { prefix: "/dashboard/modules/school/payment-gateways", permission: "payment_gateways:write" },
  // account-numbers = the school's collection bank account (fee-side) → payments.
  { prefix: "/dashboard/modules/school/account-numbers", permission: "payments:write" },
  // accounts-setup reads the ledger chart of accounts → finance_admin.
  { prefix: "/dashboard/modules/school/accounts-setup", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/discounts", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/sales-monitor", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/warehouse", permission: "payments:write" },
  // Store Pickup: finance clerks manage points/tickets; cashiers only mark collected.
  // Page reachable by EITHER — the collect action is store:sell, everything else write.
  { prefix: "/dashboard/modules/school/store-pickup", permission: "payments:write", anyOf: ["store:sell"] },
  { prefix: "/dashboard/modules/school/store-frontdesk", permission: "store:sell" },
  // Budget, Salary Advance, Bonus/Reduction, Finance Reports → SENSITIVE finance.
  { prefix: "/dashboard/modules/school/budget", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/requisitions", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/request-form", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/salary-advance", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/bonus-reduction", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/appointment-manager", permission: "hr:write" },
  { prefix: "/dashboard/modules/school/finance-reports", permission: "finance_admin:read" },
  { prefix: "/dashboard/modules/school/fee-assignment", permission: "payments:write" },
  // ── Admin Management ────────────────────────────────────────────────────
  { prefix: "/dashboard/modules/school/deactivated-users", permission: "users:write" },
  // Planned stubs (sidebar-complete; backend to follow) — admin-only.
  { prefix: "/dashboard/modules/school/week-entries", permission: "settings:read" },
  // Result Publish is a grade operation — gate on school:write (its publish endpoint
  // is school:write), so managers + org_admin (school:*) see it, not just settings holders.
  // Publish Report is an ADMIN action — hidden from teachers. (It drives the shared
  // gradebook publish; teachers still publish their own grades from the Gradebook.)
  { prefix: "/dashboard/modules/school/result-publish", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/user-roles", permission: "roles:write" },
  // ── Medicals module (confidential — medical:read) ───────────────────────
  { prefix: "/dashboard/modules/school/medical-dashboard", permission: "medical:read" },
  { prefix: "/dashboard/modules/school/medical-analysis", permission: "medical:read" },
];

/** Permission required to view `pathname`, or null when the route is open to
 *  any authenticated user (dashboard home, messenger, news feed, profile, the
 *  personal "my-" pages). Longest matching prefix wins. */
function matchRoute(pathname: string): RouteAccess | null {
  let best: RouteAccess | null = null;
  for (const entry of ROUTE_ACCESS) {
    const matches = pathname === entry.prefix || pathname.startsWith(entry.prefix + "/");
    if (matches && (!best || entry.prefix.length > best.prefix.length)) {
      best = entry;
    }
  }
  return best;
}

export function permissionForPath(pathname: string): string | null {
  const best = matchRoute(pathname);
  return best ? best.permission : null;
}

/** True if `hasPermission` satisfies the access rule for `pathname`. An unmapped
 *  route is open to any authenticated user. Honours `anyOf` (OR semantics). */
export function canAccessPath(
  pathname: string,
  hasPermission: (permission: string) => boolean,
): boolean {
  const best = matchRoute(pathname);
  if (!best) return true;
  if (best.anyOf && best.anyOf.length) {
    return hasPermission(best.permission) || best.anyOf.some(hasPermission);
  }
  return hasPermission(best.permission);
}
