"use client";

import { memo, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  LayoutDashboard, BarChart3, Users, Settings, LogOut,
  GraduationCap, Heart, Briefcase, Package, DollarSign,
  HelpCircle, ChevronDown, Building2, Stethoscope,
  Calendar, ClipboardList, ClipboardCheck, Users2, BookOpen, Bell, Shield, ShieldCheck,
  FileText, Wallet, Clock, UserCheck, Award,
  BookMarked, School, Microscope, Pill, BedDouble, Activity,
  Receipt, BadgeDollarSign, FolderOpen, BarChart, Star,
  UserCog, ShoppingCart, Truck, Contact, HandshakeIcon,
  User, NotebookPen, MonitorCheck, HeartHandshake, MessageSquare,
  Camera, MessageCircle, Users as UsersIcon, UserCircle, Cake,
  CalendarClock, Gavel, Newspaper, Radio, Library, Bus, ArrowLeftRight,
  FileQuestion, X, LifeBuoy, Settings2, KeyRound, Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/branding/Brand";
import { useAuthStore, type ActiveRole } from "@/lib/store";
import { effectiveModulesForOrg, moduleAllowedForOrg } from "@/lib/workspace";
import { canAccessPath } from "@/lib/access";
import { useLogout } from "@/hooks/useAuth";
import { markNavClick } from "@/lib/perf";

const CORE_NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  // Phase 6.3 role-specific shortcuts. These are personal pages with no module
  // permission — their data is resolved + ownership-scoped server-side from the
  // caller's identity, so they're shown by the active VIEW-role rather than a
  // permission: a student only ever sees "My Timetable", a parent "My Children".
  { href: "/dashboard/my-children", label: "My Children", icon: UserCircle, roleOnly: "parent" as ActiveRole },
  { href: "/dashboard/my-children/attendance", label: "Attendance", icon: ClipboardList, roleOnly: "parent" as ActiveRole },
  { href: "/dashboard/my-children/payments", label: "Pay Fees", icon: BadgeDollarSign, roleOnly: "parent" as ActiveRole },
  { href: "/dashboard/my-timetable", label: "My Timetable", icon: Calendar, roleOnly: "student" as ActiveRole },
  { href: "/dashboard/my-library", label: "My Library", icon: Library, roleOnly: "student" as ActiveRole },
  { href: "/dashboard/my-classes", label: "My Classes", icon: School, roleOnly: "teacher" as ActiveRole },
  { href: "/dashboard/my-classes/attendance", label: "Class Attendance", icon: ClipboardList, roleOnly: "teacher" as ActiveRole },
  // Everything below is permission-gated via the shared access map (lib/access).
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/users", label: "Users", icon: Users },
  { href: "/dashboard/hrm", label: "HR Manager", icon: Briefcase },
  { href: "/dashboard/hrm/my-info", label: "My HRM Info", icon: UserCircle },
  { href: "/dashboard/hrm/leave", label: "My Leave", icon: CalendarClock },
  { href: "/dashboard/hrm/leave/admin", label: "Leave Admin", icon: Gavel },
  { href: "/messenger", label: "Messenger", icon: MessageSquare },
  { href: "/news-feed", label: "News Feed", icon: Newspaper },
  { href: "/dashboard/notifications", label: "Notifications", icon: Bell },
  { href: "/dashboard/audit", label: "Audit Log", icon: Shield },
];


// Phase 7: visibility is now driven entirely by PERMISSIONS, not hardcoded role
// allow-lists. A nav item is shown when:
//   • it is `roleOnly` → the active view-role matches (personal "my-" pages), OR
//   • the shared access map (lib/access) requires no permission for its href, OR
//   • the user holds the permission the access map requires for its href.
// The same access map backs RouteGuard, so a hidden link is also unreachable by
// direct URL. `hasPermission` honours the broad→fine scope hierarchy, so a
// teacher's broad `school:read` reveals every core teaching item automatically.
function navItemVisible(
  item: { href: string; roleOnly?: ActiveRole },
  roleScope: ActiveRole | null,
  hasPermission: (permission: string) => boolean,
): boolean {
  if (item.roleOnly) return roleScope === item.roleOnly;
  // Real pages: the shared access map decides. A null requirement means the
  // route is open to any authenticated user. Strip any ?query (e.g. deep-linked
  // School Setup tabs) so the access map matches on the base path, not the full URL.
  return canAccessPath(item.href.split("?")[0], hasPermission);
}

interface NavItem {
  href: string;
  label: string;
  icon: any;
}

interface ModuleSection {
  items: NavItem[];
  label: string;
  icon: any;
  key: string;
  /** Primary workspace module required for the section to render. */
  requiredModule: string;
}

// Phase 7+ navigation, grouped EduCare-style. Every item is a REAL page,
// permission-gated via the shared access map — the build-out is complete and
// no "Coming soon" placeholders remain. Non-admins only ever see the real
// items their permissions allow.
const MODULE_SECTIONS: ModuleSection[] = [
  {
    key: "academics",
    requiredModule: "school",
    label: "Academics",
    icon: GraduationCap,
    items: [
      { href: "/dashboard/modules/school/classes", label: "Classes", icon: School },
      { href: "/dashboard/modules/school/subjects", label: "Subjects", icon: BookMarked },
      { href: "/dashboard/modules/school/timetable", label: "Timetable", icon: Calendar },
      { href: "/dashboard/modules/school/lessons", label: "Lesson Planner", icon: NotebookPen },
      { href: "/dashboard/modules/school/exams", label: "Exams & Results", icon: Award },
      { href: "/dashboard/modules/school/grades", label: "Gradebook", icon: BookOpen },
      { href: "/dashboard/modules/school/report-cards", label: "Report Cards", icon: FileText },
      { href: "/dashboard/modules/school/eclassroom", label: "eClassroom", icon: NotebookPen },
      { href: "/dashboard/modules/school/cbt", label: "CBT", icon: MonitorCheck },
      { href: "/dashboard/modules/school/cbt/question-bank", label: "Question Bank", icon: FileQuestion },
      { href: "/dashboard/modules/school/cbt/results", label: "Result Manager", icon: BarChart3 },
      { href: "/dashboard/modules/school/cbt/interventions", label: "Interventions", icon: LifeBuoy },
      { href: "/dashboard/modules/school/cbt/settings", label: "CBT Setup", icon: Settings2 },
      { href: "/dashboard/modules/school/cbt/live", label: "Live Classes", icon: Radio },
      // Batch 3 (Academic Records) — shipped. subject-selection → school:subjects:read;
      // mark-books → school:grades:read; report-workflow → school:reports:write.
      { href: "/dashboard/modules/school/subject-selection", label: "Subject Selection", icon: BookMarked },
      { href: "/dashboard/modules/school/mark-books", label: "Mark Books & Transcripts", icon: FileText },
      { href: "/dashboard/modules/school/report-workflow", label: "Report Workflow", icon: FolderOpen },
    ],
  },
  {
    key: "students",
    requiredModule: "school",
    label: "Students",
    icon: Users2,
    items: [
      { href: "/dashboard/modules/school/students", label: "Students", icon: Users2 },
      // Batch 2 (Admissions & Enrollment) — shipped. Permissions from the access
      // map: admissions/entrance-exams → school:admissions:read; promotion/
      // transfer/pickup → school:students:write.
      { href: "/dashboard/modules/school/students/pickup", label: "Manage Students Pickup", icon: ShieldCheck },
      { href: "/dashboard/modules/school/admissions", label: "Admissions & Enquiries", icon: Contact },
      { href: "/dashboard/modules/school/admissions/appointments", label: "Enquiry Appointment", icon: CalendarClock },
      { href: "/dashboard/modules/school/entrance-exams", label: "Entrance Exams", icon: Award },
      { href: "/dashboard/modules/school/admissions/post-entrance", label: "Post Entrance Form", icon: FileText },
      { href: "/dashboard/modules/school/admissions/acceptance", label: "Acceptance Form", icon: ClipboardCheck },
      { href: "/dashboard/modules/school/promotion", label: "Promotion Manager", icon: BarChart3 },
      { href: "/dashboard/modules/school/transfer", label: "Transfer Manager", icon: UserCog },
    ],
  },
  {
    key: "pastoral",
    requiredModule: "school",
    label: "Pastoral & Welfare",
    icon: HeartHandshake,
    items: [
      { href: "/dashboard/modules/school/behaviour", label: "Pastoral Care", icon: HeartHandshake },
      { href: "/dashboard/modules/school/attendance", label: "Attendance", icon: ClipboardList },
      { href: "/dashboard/modules/school/attendance/dashboard", label: "Attendance Insights", icon: BarChart3 },
      { href: "/dashboard/modules/school/attendance/setup", label: "Attendance Setup", icon: Settings2 },
      { href: "/dashboard/modules/school/clubs", label: "Clubs & Activities", icon: Users2 },
      { href: "/dashboard/modules/school/journals", label: "Photo Journals", icon: Camera },
      { href: "/dashboard/modules/school/remarks", label: "Weekly Remarks", icon: MessageCircle },
      // Batch 3 — shipped. Merit & Awards (conduct points + academic awards),
      // gated school:behaviour:read (staff-only; students/parents lack it).
      { href: "/dashboard/modules/school/merits", label: "Merit & Awards", icon: Award },
      // Batch 4 (Pastoral, Boarding & Health) — shipped. hostel/exeat →
      // school:hostel:read; mentor → school:behaviour:read; medicals →
      // medical:read (confidential: org_admin + nurse only, NOT general staff).
      { href: "/dashboard/modules/school/hostel", label: "Hostel / Boarding", icon: BedDouble },
      { href: "/dashboard/modules/school/exeat", label: "Exeat Requests", icon: FileText },
      { href: "/dashboard/modules/school/mentor", label: "Mentor Reports", icon: UserCheck },
    ],
  },
  {
    // Educare-style Feedback section. Form / My Feedback are self-service (any
    // school user); Settings / Manager gate school:feedback:write; Daily Report,
    // Student Daily Report and CRM are staff surfaces on the broad school scopes.
    key: "feedback",
    requiredModule: "school",
    label: "Feedback",
    icon: MessageSquare,
    items: [
      { href: "/dashboard/modules/school/feedback/settings", label: "Feedback Settings", icon: Settings2 },
      { href: "/dashboard/modules/school/feedback", label: "Feedback Form", icon: MessageSquare },
      { href: "/dashboard/modules/school/feedback/mine", label: "My Feedback", icon: MessageCircle },
      { href: "/dashboard/modules/school/feedback/manage", label: "Feedback Manager", icon: FolderOpen },
      { href: "/dashboard/modules/school/feedback/daily-reports", label: "Daily Report", icon: FileText },
      { href: "/dashboard/modules/school/feedback/student-daily-reports", label: "Student Daily Report", icon: UserCheck },
      { href: "/dashboard/modules/school/feedback/crm", label: "CRM", icon: Contact },
    ],
  },
  {
    // Educare-style Behaviour Tracker admin cluster. Manage/Sub-manage drive the
    // category→sub-category taxonomy; Awardings reuses the existing Merit & Awards
    // page; Levels + Settings are new. All ride school:behaviour (staff config).
    // The daily behaviour LOGGING surface stays as "Pastoral Care" above.
    key: "behaviour-tracker",
    requiredModule: "school",
    label: "Behaviour Tracker",
    icon: BookMarked,
    items: [
      { href: "/dashboard/modules/school/behaviour/categories", label: "Manage Behaviour Tracker", icon: BookOpen },
      { href: "/dashboard/modules/school/behaviour/subcategories", label: "Sub-manage Behaviour Tracker", icon: FolderOpen },
      { href: "/dashboard/modules/school/merits", label: "Manage Awardings", icon: Award },
      { href: "/dashboard/modules/school/behaviour/levels", label: "Manage Behaviour Levels", icon: BarChart },
      { href: "/dashboard/modules/school/behaviour/settings", label: "Behaviour Tracker Settings", icon: Settings2 },
    ],
  },
  {
    // Educare-style Medicals module. "Manage Medicals" reuses the existing
    // confidential medical records page; Dashboard + Analysis are new reporting
    // surfaces. (Medical Setup is deferred — needs a new config model.)
    key: "medicals",
    requiredModule: "school",
    label: "Medicals",
    icon: Stethoscope,
    items: [
      { href: "/dashboard/modules/school/medical-dashboard", label: "Medical Dashboard", icon: Stethoscope },
      { href: "/dashboard/modules/school/medicals", label: "Manage Medicals", icon: Pill },
      { href: "/dashboard/modules/school/medical-analysis", label: "Medical Analysis", icon: BarChart },
    ],
  },
  {
    key: "people",
    requiredModule: "school",
    label: "Staff Management",
    icon: Briefcase,
    items: [
      { href: "/dashboard/modules/school/teachers", label: "Teachers", icon: UserCheck },
      { href: "/dashboard/modules/school/staff", label: "Staff", icon: UsersIcon },
      { href: "/dashboard/modules/school/ratings", label: "Teacher Ratings", icon: Star },
      // Batch 1 (People & HR) — shipped. Permission resolved from the access map:
      // parents → school:parents:read; the two HR surfaces → hr:write.
      { href: "/dashboard/modules/school/parents", label: "Parents Directory", icon: Contact },
      { href: "/dashboard/modules/school/staff-assessment/setup", label: "Setup Staff Assessment", icon: Settings2 },
      { href: "/dashboard/modules/school/staff-assessment", label: "Staff Assessment", icon: ClipboardList },
      { href: "/dashboard/modules/school/staff-assessment/manage", label: "Manage Staff Assessment", icon: FolderOpen },
      { href: "/dashboard/modules/school/talent-pool", label: "Talent Pool", icon: Star },
    ],
  },
  {
    key: "finance",
    requiredModule: "school",
    label: "Finance",
    icon: DollarSign,
    // Full Educare Finance order. Real pages where backend exists; the rest are
    // clearly-labelled "planned" stubs (payments:write, admin-only).
    items: [
      { href: "/dashboard/modules/school/payment-gateways", label: "Payment Gateways", icon: Wallet },
      { href: "/dashboard/modules/school/accounts", label: "Chart Of Accounts", icon: BookOpen },
      { href: "/dashboard/modules/school/account-numbers", label: "Account Numbers", icon: BookMarked },
      { href: "/dashboard/modules/school/accounts-setup", label: "Accounts Setup", icon: Settings },
      { href: "/dashboard/modules/school/discounts", label: "Manage Discounts", icon: Receipt },
      { href: "/dashboard/modules/school/invoices", label: "Invoice Center", icon: Receipt },
      { href: "/dashboard/modules/school/sales-monitor", label: "Sales Monitor", icon: BarChart3 },
      { href: "/dashboard/modules/school/store", label: "Store Inventory", icon: Package },
      { href: "/dashboard/modules/school/warehouse", label: "Warehouse", icon: Building2 },
      { href: "/dashboard/modules/school/store-pickup", label: "Store Pickup Unit", icon: Truck },
      { href: "/dashboard/modules/school/store-frontdesk", label: "Store FrontDesk", icon: ShoppingCart },
      { href: "/dashboard/modules/school/budget", label: "Budget Mgt", icon: Wallet },
      { href: "/dashboard/modules/school/requisitions", label: "Requisitions", icon: ClipboardList },
      { href: "/dashboard/modules/school/request-form", label: "Request Form", icon: FileText },
      { href: "/dashboard/modules/school/direct-posts", label: "Direct Posts", icon: BookOpen },
      { href: "/dashboard/modules/school/direct-transfer", label: "Direct Transfer", icon: ArrowLeftRight },
      { href: "/dashboard/modules/school/petty-cash", label: "Petty Cash", icon: Wallet },
      { href: "/dashboard/modules/school/salary-advance", label: "Salary Advance", icon: BadgeDollarSign },
      { href: "/dashboard/modules/school/payroll", label: "Payroll", icon: BadgeDollarSign },
      { href: "/dashboard/modules/school/bonus-reduction", label: "Bonus/Reduction Pack", icon: DollarSign },
      { href: "/dashboard/modules/school/appointment-manager", label: "Appointment Manager", icon: CalendarClock },
      { href: "/dashboard/modules/school/finance-overview", label: "Broad View", icon: BarChart3 },
      { href: "/dashboard/modules/school/financial-statements", label: "Fin. Statements", icon: BarChart },
      { href: "/dashboard/modules/school/cash-txns", label: "Cash Transactions", icon: DollarSign },
      { href: "/dashboard/modules/school/finance-reports", label: "Reports", icon: BarChart },
      // Ours (not in Educare's finance list) — kept.
      { href: "/dashboard/modules/school/fee-assignment", label: "Fee Assignment", icon: Wallet },
      { href: "/dashboard/modules/school/fees", label: "Fee Management", icon: Wallet },
      { href: "/dashboard/billing", label: "Billing & Subscription", icon: BadgeDollarSign },
    ],
  },
  {
    key: "operations",
    requiredModule: "school",
    label: "Operations",
    icon: Package,
    items: [
      { href: "/dashboard/modules/school/transport", label: "Transport", icon: Bus },
      { href: "/dashboard/modules/school/tuckshop", label: "Tuckshop", icon: ShoppingCart },
      { href: "/dashboard/modules/school/library", label: "Library", icon: Library },
      { href: "/dashboard/modules/school/sms", label: "Bulk SMS", icon: MessageSquare },
      // Batch 6 (money features) — shipped: ledger-backed student money.
      { href: "/dashboard/modules/school/wallet", label: "Wallet Manager", icon: Wallet },
      { href: "/dashboard/modules/school/pocketmoney", label: "PocketMoney", icon: BadgeDollarSign },
      { href: "/dashboard/modules/school/cooperative", label: "Cooperative", icon: HandshakeIcon },
      // Batch 6 (non-financial) — shipped. Calendar → school:read; Facility +
      // Visitor (safeguarding) → school_admin:read.
      { href: "/dashboard/modules/school/calendar", label: "Calendar & Planner", icon: Calendar },
      { href: "/dashboard/modules/school/visitor", label: "Visitor Management", icon: UserCheck },
    ],
  },
  {
    // Educare "Facility Management" — 8 children under the school_admin:facility
    // scope (org_admin + manager inherit it; the dedicated `facilities` role holds
    // only it). Requisitions run the tiered approval levels; Audit Trail is a
    // filtered view over the global audit log.
    key: "facility-management",
    requiredModule: "school",
    label: "Facility Management",
    icon: Building2,
    items: [
      { href: "/dashboard/modules/school/facility", label: "Facility List", icon: Building2 },
      { href: "/dashboard/modules/school/facility/complaints", label: "Facility Complaints", icon: MessageSquare },
      { href: "/dashboard/modules/school/facility/inspections", label: "Facility Inspections", icon: ClipboardList },
      { href: "/dashboard/modules/school/facility/maintenance", label: "Facility Maintenance", icon: Wrench },
      { href: "/dashboard/modules/school/facility/requisitions", label: "Facility Requisitions", icon: Receipt },
      { href: "/dashboard/modules/school/facility/configuration", label: "Configuration", icon: Settings2 },
      { href: "/dashboard/modules/school/facility/report", label: "Facility Report", icon: BarChart },
      { href: "/dashboard/modules/school/facility/audit", label: "Audit Trail", icon: FileText },
    ],
  },
  {
    // Educare "Admin Management" — all 7 reference children. Audit Trail surfaces
    // the existing Core Audit Log; Biometric + Custom Field reuse the platform
    // pages; "Manage User Roles & Password" points at the canonical Users page
    // (role assignment + password reset) — the single source of truth, surfaced
    // here for menu parity rather than duplicated.
    key: "admin-management",
    requiredModule: "school",
    label: "Admin Management",
    icon: Shield,
    items: [
      { href: "/dashboard/audit", label: "Audit Trail", icon: FileText },
      { href: "/dashboard/modules/school/deactivated-users", label: "Manage Deactivated Users", icon: UserCog },
      { href: "/dashboard/modules/school/week-entries", label: "Manage Week Entries", icon: CalendarClock },
      { href: "/dashboard/modules/school/result-publish", label: "Result Publish Helper", icon: ClipboardList },
      { href: "/dashboard/users", label: "Manage User Roles & Password", icon: KeyRound },
      { href: "/dashboard/modules/school/biometric", label: "Manage Biometric", icon: Activity },
      { href: "/dashboard/modules/school/custom-fields", label: "Manage Custom Field", icon: FolderOpen },
    ],
  },
  {
    // School Setup — its own top-level section (peer of Admin Management), matching
    // Educare where School Setup is a distinct route. Children deep-link the config
    // tabs of the /school-setup page (?tab=…); the sidebar's tab-aware active
    // detection highlights the current tab.
    key: "school-setup",
    requiredModule: "school",
    label: "School Setup",
    icon: Settings,
    items: [
      { href: "/dashboard/modules/school/school-setup?tab=sections", label: "School Types", icon: School },
      { href: "/dashboard/modules/school/school-setup?tab=sessions", label: "Manage Sessions", icon: CalendarClock },
      { href: "/dashboard/modules/school/school-setup?tab=houses", label: "Houses", icon: Building2 },
      { href: "/dashboard/modules/school/school-setup?tab=bands", label: "Grading Bands", icon: Award },
      { href: "/dashboard/modules/school/school-setup?tab=reports", label: "Report Config", icon: FileText },
    ],
  },
  {
    key: "administration",
    requiredModule: "school",
    label: "Administration",
    icon: Settings2,
    items: [
      // Batch 7 (Administration & Platform) — shipped. All settings:read gated.
      { href: "/dashboard/modules/school/voting", label: "Voting System", icon: Gavel },
      { href: "/dashboard/modules/school/mailbox", label: "Mailbox", icon: MessageSquare },
      { href: "/dashboard/modules/school/mobile", label: "Mobile Manager", icon: MonitorCheck },
    ],
  },
  // Hospital & Business workspaces are retired for the Fairview School Portal.
  // Only the school workspace is surfaced. (Backend deprecation strategy is
  // unchanged — those routes are simply no longer mounted or navigated to.)
];

// One nav-row recipe used by every clickable item (core, section headers, sub
// items, footer) so spacing, font size/weight, icon size and states stay
// identical across the whole sidebar. Active = a light tint of the brand (a
// "lighter shade of the base") with a rounded corner; hover = a subtle slate wash.
// Dark-green rail (Educare-style). Idle text is a soft near-white green; the
// active row is a lighter tint (white/10 reads as a lighter green over the base)
// with bright white text; hover is a very subtle white overlay.
const NAV_ROW = "flex items-center gap-3 px-3 py-1 rounded-md text-sm font-semibold transition-colors";
const NAV_ACTIVE = "bg-white/10 text-white";
const NAV_IDLE = "text-green-50/75 hover:bg-white/5 hover:text-white";
const NAV_ICON = 18;      // uniform outline icon size across all items
const NAV_STROKE = 1.75;  // uniform stroke width

export function Sidebar({ open = false, onClose }: { open?: boolean; onClose?: () => void } = {}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentTab = searchParams.get("tab");
  const { user, org, activeRole, hasPermission } = useAuthStore();
  const logout = useLogout();
  const roleScope = moduleAllowedForOrg(org, "school") ? activeRole : "admin";

  // The backend returns workspace-filtered modules. We still evaluate the
  // industry locally so stale persisted state cannot flash another product
  // shell while /me is hydrating.
  // If the org hasn't hydrated yet, render nothing module-side to avoid
  // a flash of the wrong product shell.
  const enabled = org ? effectiveModulesForOrg(org) : undefined;

  // Longest-prefix-wins so exactly ONE item highlights. Without this, a base
  // route (e.g. Facility List `/…/facility`) would also match its deeper sibling
  // routes (`/…/facility/complaints`) via startsWith and double-highlight.
  const activeHref = useMemo(() => {
    // Match on the base path (query stripped) so deep-linked tabs like
    // `/school-setup?tab=houses` resolve to their page for the longest-prefix win.
    const candidates = [
      ...CORE_NAV.map((i) => i.href),
      ...MODULE_SECTIONS.flatMap((s) => s.items.map((i) => i.href)),
      "/dashboard/profile", "/dashboard/settings", "/support",
    ].map((h) => h.split("?")[0]);
    let best = "";
    for (const h of candidates) {
      const hit = pathname === h || (h !== "/dashboard" && pathname.startsWith(h + "/"));
      if (hit && h.length > best.length) best = h;
    }
    return best;
  }, [pathname]);
  // A plain item is active when its base path is the winner. A tabbed item
  // (href carries ?tab=) is active only when its tab is the current one — so the
  // four School Setup sub-items each highlight for their own tab (default: the
  // first, "sessions").
  const isActive = useCallback((href: string) => {
    const [base, query] = href.split("?");
    if (base !== activeHref) return false;
    if (!query) return true;
    const tab = new URLSearchParams(query).get("tab");
    return !tab || (currentTab || "sessions") === tab;
  }, [activeHref, currentTab]);

  // Phase 7: build the visible core-nav list, filtered by permission (+ the
  // active view-role for personal pages). Depends on `user`/`org` so it
  // recomputes when the signed-in identity or its permissions change.
  const visibleCoreNav = useMemo(
    () => CORE_NAV.filter((item) => navItemVisible(item, roleScope ?? null, hasPermission)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [roleScope, user, org],
  );

  // Pre-filter module sections by module AND by permission. A teacher's broad
  // school:read reveals the core teaching items; admin-only items (Staff, Bulk
  // SMS, Transport, Tuckshop, Ratings, Insights) require school_admin/payments
  // which teachers don't hold, so they stay hidden.
  const visibleSections = useMemo(() => {
    if (!enabled) return [] as ModuleSection[];
    return MODULE_SECTIONS
      .filter((s) => moduleAllowedForOrg(org, s.requiredModule as "school" | "business" | "hospital"))
      .map((s) => ({
        ...s,
        items: s.items.filter((it) => navItemVisible(it, roleScope ?? null, hasPermission)),
      }))
      .filter((s) => s.items.length > 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, org, roleScope, user]);

  return (
    <>
      {/* Mobile backdrop — tap to dismiss the drawer */}
      {open && (
        <div
          className="no-print lg:hidden fixed inset-0 bg-slate-900/40 z-40"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "no-print fixed left-0 top-0 h-screen w-60 max-w-[85vw] bg-[#14432f] border-r border-white/10 flex flex-col z-50 shadow-sm",
          "transition-transform duration-200 ease-out lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 py-3.5 border-b border-white/10">
        <BrandMark className="h-8 shrink-0" priority />
        <div className="min-w-0 flex-1">
          <p className="text-base font-black text-white truncate leading-tight">{org?.name || "Fairview School Portal"}</p>
          <p className="text-[10px] font-bold uppercase tracking-wider text-green-200/70 truncate">
            School Portal
          </p>
        </div>
        {/* Mobile: close the drawer */}
        <button onClick={onClose} aria-label="Close menu" className="lg:hidden p-1.5 -mr-1.5 rounded-lg text-green-100 hover:bg-white/10">
          <X size={18} />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-2 space-y-0.5">
        {/* Core */}
        <div>
          <p className="px-2.5 mb-0.5 text-[10px] font-bold uppercase tracking-widest text-green-200/70">Core</p>
          <div className="space-y-0">
            {visibleCoreNav.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => markNavClick(href)}
                className={cn(NAV_ROW, isActive(href) ? NAV_ACTIVE : NAV_IDLE)}
              >
                <Icon size={NAV_ICON} strokeWidth={NAV_STROKE} className="shrink-0" />
                <span className="truncate">{label}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* Skeleton while org hydrates — prevents a flash of the wrong shell. */}
        {!org && <ModuleSectionsSkeleton />}

        {/* Render only sections that belong to the current workspace. */}
        {org && visibleSections.map((section) => (
          <CollapsibleSection
            key={section.key}
            section={section}
            isActive={isActive}
          />
        ))}
      </nav>

      {/* Bottom */}
      <div className="px-2.5 pb-3 pt-2 border-t border-white/10 space-y-0">
        <Link
          href="/dashboard/profile"
          className={cn(NAV_ROW, isActive("/dashboard/profile") ? NAV_ACTIVE : NAV_IDLE)}
        >
          <User size={NAV_ICON} strokeWidth={NAV_STROKE} className="shrink-0" />
          <span className="truncate">Profile</span>
        </Link>
        {hasPermission("settings:read") && (
          <Link
            href="/dashboard/settings"
            className={cn(NAV_ROW, isActive("/dashboard/settings") ? NAV_ACTIVE : NAV_IDLE)}
          >
            <Settings size={NAV_ICON} strokeWidth={NAV_STROKE} className="shrink-0" />
            <span className="truncate">Settings</span>
          </Link>
        )}
        <Link href="/support" className={cn(NAV_ROW, NAV_IDLE)}>
          <HelpCircle size={NAV_ICON} strokeWidth={NAV_STROKE} className="shrink-0" />
          <span className="truncate">Support</span>
        </Link>
        <button
          onClick={logout}
          className={cn(NAV_ROW, "w-full text-left text-red-300 hover:bg-red-500/10 hover:text-red-200")}
        >
          <LogOut size={NAV_ICON} strokeWidth={NAV_STROKE} className="shrink-0" />
          <span className="truncate">Sign out</span>
        </button>

        {/* User card */}
        {user && (
          <Link href="/dashboard/profile" className="block mt-3">
            <div className="px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-white/15 flex items-center justify-center text-white text-xs font-bold shrink-0 overflow-hidden">
                  {user.avatar_url ? (
                    <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    user.full_name.charAt(0)
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-white truncate">{user.full_name}</p>
                  <p className="text-[10px] text-green-200/70 truncate">{user.email}</p>
                </div>
              </div>
            </div>
          </Link>
        )}
      </div>
      </aside>
    </>
  );
}

function ModuleSectionsSkeleton() {
  return (
    <div className="space-y-5" aria-hidden>
      {[0, 1].map((i) => (
        <div key={i}>
          <div className="px-3 mb-2 h-3 w-20 bg-white/10 rounded animate-pulse" />
          <div className="space-y-1">
            {[0, 1, 2, 3].map((j) => (
              <div key={j} className="h-8 mx-1 bg-white/5 rounded-lg animate-pulse" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

const CollapsibleSection = memo(function CollapsibleSection({
  section,
  isActive,
}: {
  section: ModuleSection;
  isActive: (href: string) => boolean;
}) {
  const ModuleIcon = section.icon;
  const containsActive = section.items.some((it) => isActive(it.href));
  // Collapsed by default; the section that holds the current route opens so its
  // active child is visible (and re-opens if you navigate into it). Other
  // sections stay closed until the user clicks their row.
  const [open, setOpen] = useState(containsActive);
  useEffect(() => {
    if (containsActive) setOpen(true);
  }, [containsActive]);

  // A collapsed section that holds the active route gets a subtle active tint on
  // its own row, so the current module is clear even before you expand it.
  const headerHint = containsActive && !open;

  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={cn(
          NAV_ROW, "w-full",
          headerHint ? "bg-white/10 text-white hover:bg-white/15" : NAV_IDLE,
        )}
      >
        <ModuleIcon size={NAV_ICON} strokeWidth={NAV_STROKE} className="shrink-0" />
        <span className="flex-1 text-left truncate">{section.label}</span>
        <ChevronDown
          size={16}
          className={cn("shrink-0 text-green-200/60 transition-transform duration-200", !open && "-rotate-90")}
        />
      </button>
      {open && (
        <div className="mt-px ml-4 pl-1.5 border-l border-white/10 space-y-0 animate-fade-in">
          {section.items.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => markNavClick(href)}
              className={cn(NAV_ROW, isActive(href) ? NAV_ACTIVE : NAV_IDLE)}
            >
              <Icon size={NAV_ICON} strokeWidth={NAV_STROKE} className="shrink-0" />
              <span className="truncate">{label}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
});
