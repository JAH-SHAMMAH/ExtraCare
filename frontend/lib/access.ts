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
  { prefix: "/dashboard/hrm/leave", permission: "hr:read" },
  // Phase 4: Recruitment + Disciplinary — confidential HR admin (hr:write).
  { prefix: "/dashboard/hrm/recruitment", permission: "hr:write" },
  // Self-service: a staff member's OWN disciplinary record (longest-prefix wins,
  // so this hr:read route sits under the hr:write disciplinary parent).
  { prefix: "/dashboard/hrm/disciplinary/my-actions", permission: "hr:read" },
  { prefix: "/dashboard/hrm/disciplinary", permission: "hr:write" },
  // Phase 4 Batch 2: Performance (hr:write); Access Control = role mgmt (roles:write, admin).
  { prefix: "/dashboard/hrm/performance", permission: "hr:write" },
  { prefix: "/dashboard/hrm/access-control", permission: "roles:write" },
  { prefix: "/dashboard/hrm", permission: "hr:write" },

  // ── School module (fine-grained per feature) ───────────────────────
  { prefix: "/dashboard/modules/school/students", permission: "school:students:read" },
  { prefix: "/dashboard/modules/school/teachers", permission: "school:teachers:read" },
  { prefix: "/dashboard/modules/school/staff", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/classes", permission: "school:classes:read" },
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
  { prefix: "/dashboard/modules/school/timetable", permission: "school:timetable:read" },
  { prefix: "/dashboard/modules/school/lessons", permission: "school:lessons:write" },
  { prefix: "/dashboard/modules/school/library", permission: "school:library:read" },
  { prefix: "/dashboard/modules/school/sms", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/transport", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/report-cards", permission: "school:reports:read" },
  { prefix: "/dashboard/modules/school/fees", permission: "payments:read" },
  { prefix: "/dashboard/modules/school/ratings", permission: "school_admin:read" },
  { prefix: "/dashboard/modules/school/eclassroom", permission: "school:classroom:read" },
  // Question Bank holds correct answers — staff-only (school:read), stricter than
  // the cbt scope students hold to sit tests. Longer prefix wins over /cbt above.
  { prefix: "/dashboard/modules/school/cbt/question-bank", permission: "school:read" },
  // Result Manager exposes every student's scores + correct answers — staff-only.
  { prefix: "/dashboard/modules/school/cbt/results", permission: "school:read" },
  // Interventions surface flagged students' scores; Setup edits org-wide defaults — staff-only.
  { prefix: "/dashboard/modules/school/cbt/interventions", permission: "school:read" },
  { prefix: "/dashboard/modules/school/cbt/settings", permission: "school:read" },
  // Admin CBT ops (import / export / reset / remark) — staff-only, like the bank
  // and Result Manager (NOT the student cbt scope which sits tests).
  { prefix: "/dashboard/modules/school/cbt/import", permission: "school:read" },
  { prefix: "/dashboard/modules/school/cbt/export", permission: "school:read" },
  { prefix: "/dashboard/modules/school/cbt/reset", permission: "school:read" },
  { prefix: "/dashboard/modules/school/cbt/remark", permission: "school:read" },
  { prefix: "/dashboard/modules/school/cbt", permission: "school:cbt:read" },
  { prefix: "/dashboard/modules/school/behaviour", permission: "school:behaviour:read" },
  // Feedback section: Form / My Feedback inherit feedback:read (self-service);
  // Settings / Manager require feedback:write; Daily/Student-Daily/CRM are staff
  // surfaces on the broad school scopes. Longest-prefix match wins.
  { prefix: "/dashboard/modules/school/feedback/settings", permission: "school:feedback:write" },
  { prefix: "/dashboard/modules/school/feedback/manage", permission: "school:feedback:write" },
  { prefix: "/dashboard/modules/school/feedback/daily-reports", permission: "school:read" },
  { prefix: "/dashboard/modules/school/feedback/student-daily-reports", permission: "school:read" },
  // CRM is a view over Admissions data — gate it on the admissions scope.
  { prefix: "/dashboard/modules/school/feedback/crm", permission: "school:admissions:read" },
  { prefix: "/dashboard/modules/school/feedback", permission: "school:feedback:read" },
  { prefix: "/dashboard/modules/school/clubs", permission: "school:clubs:read" },
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
  { prefix: "/dashboard/modules/school/report-workflow", permission: "school:reports:write" },
  { prefix: "/dashboard/modules/school/merits", permission: "school:behaviour:read" },

  // ── Batch 4: Pastoral, Boarding & Health ───────────────────────────────
  // Hostel + Exeat ride school:hostel; Mentor reports ride school:behaviour.
  // Medicals is CONFIDENTIAL: gated by the dedicated `medical` namespace, which
  // the broad school:read hierarchy does NOT reach — only org_admin + nurse.
  { prefix: "/dashboard/modules/school/hostel", permission: "school:hostel:read" },
  { prefix: "/dashboard/modules/school/exeat", permission: "school:hostel:read" },
  { prefix: "/dashboard/modules/school/mentor", permission: "school:behaviour:read" },
  { prefix: "/dashboard/modules/school/medicals", permission: "medical:read" },

  // ── Batch 5: Finance & Accounting ──────────────────────────────────────
  // Admin finance gated at payments:WRITE (not read): parents hold
  // payments:read to pay fees, so view-gating on read would leak the ledger /
  // payroll to them. write keeps it to manager / accountant / admin.
  { prefix: "/dashboard/modules/school/accounts", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/invoices", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/payroll", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/petty-cash", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/cash-txns", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/store", permission: "payments:write" },

  // ── Batch 6: Wallet / PocketMoney + Cooperative ────────────────────────
  // Wallet Manager + Cooperative are admin money surfaces → payments:write
  // (parents who hold payments:read for fees don't see them). PocketMoney is the
  // spend surface → the dedicated wallet:spend scope (till staff + finance roles).
  { prefix: "/dashboard/modules/school/wallet", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/pocketmoney", permission: "wallet:spend" },
  { prefix: "/dashboard/modules/school/cooperative", permission: "payments:write" },

  // ── Batch 6 non-financial ──────────────────────────────────────────────
  // Calendar rides school:read; Facility + Visitor (safeguarding) are admin-tier.
  { prefix: "/dashboard/modules/school/calendar", permission: "school:read" },
  // Facility Management: its own fine-grained scope so the dedicated `facilities`
  // role reaches it (org_admin + manager inherit via broad school_admin:read).
  { prefix: "/dashboard/modules/school/facility", permission: "school_admin:facility:read" },
  { prefix: "/dashboard/modules/school/visitor", permission: "school_admin:read" },

  // ── Batch 7: Administration & Platform (settings:* — admin only) ────────
  { prefix: "/dashboard/modules/school/school-setup", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/biometric", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/custom-fields", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/voting", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/mailbox", permission: "settings:read" },
  { prefix: "/dashboard/modules/school/mobile", permission: "settings:read" },

  // ── Educare parity — Finance additions (over the existing ledger) ───────
  { prefix: "/dashboard/modules/school/direct-posts", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/direct-transfer", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/financial-statements", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/finance-overview", permission: "payments:write" },
  // Finance parity stubs (backend to follow) — admin finance (payments:write).
  // Gateway API secrets are org_admin-only, on the SEPARATE payment_gateways
  // namespace (NOT payments:*, which accountants/managers hold). See finance.py.
  { prefix: "/dashboard/modules/school/payment-gateways", permission: "payment_gateways:write" },
  { prefix: "/dashboard/modules/school/account-numbers", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/accounts-setup", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/discounts", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/sales-monitor", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/warehouse", permission: "payments:write" },
  // Store Pickup: finance clerks manage points/tickets; cashiers only mark collected.
  // Page reachable by EITHER — the collect action is store:sell, everything else write.
  { prefix: "/dashboard/modules/school/store-pickup", permission: "payments:write", anyOf: ["store:sell"] },
  { prefix: "/dashboard/modules/school/store-frontdesk", permission: "store:sell" },
  { prefix: "/dashboard/modules/school/budget", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/requisitions", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/request-form", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/salary-advance", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/bonus-reduction", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/appointment-manager", permission: "hr:write" },
  { prefix: "/dashboard/modules/school/finance-reports", permission: "payments:write" },
  { prefix: "/dashboard/modules/school/fee-assignment", permission: "payments:write" },
  // ── Admin Management ────────────────────────────────────────────────────
  { prefix: "/dashboard/modules/school/deactivated-users", permission: "users:write" },
  // Planned stubs (sidebar-complete; backend to follow) — admin-only.
  { prefix: "/dashboard/modules/school/week-entries", permission: "settings:read" },
  // Result Publish is a grade operation — gate on school:write (its publish endpoint
  // is school:write), so managers + org_admin (school:*) see it, not just settings holders.
  { prefix: "/dashboard/modules/school/result-publish", permission: "school:write" },
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
