"use client";

import { memo, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, BarChart3, Users, Settings, LogOut,
  GraduationCap, Heart, Briefcase, Package, DollarSign,
  HelpCircle, ChevronDown, Building2, Stethoscope,
  Calendar, ClipboardList, Users2, BookOpen, Bell, Shield,
  FileText, Wallet, Clock, UserCheck, Award,
  BookMarked, School, Microscope, Pill, BedDouble, Activity,
  Receipt, BadgeDollarSign, FolderOpen, BarChart, Star,
  UserCog, ShoppingCart, Truck, Contact, HandshakeIcon,
  User, NotebookPen, MonitorCheck, HeartHandshake, MessageSquare,
  Camera, MessageCircle, Users as UsersIcon, UserCircle, Cake,
  CalendarClock, Gavel, Newspaper, Radio, Library, Bus, ArrowLeftRight,
  FileQuestion,
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
  // route is open to any authenticated user.
  return canAccessPath(item.href, hasPermission);
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
      // transfer → school:students:write.
      { href: "/dashboard/modules/school/admissions", label: "Admissions & Enquiries", icon: Contact },
      { href: "/dashboard/modules/school/entrance-exams", label: "Entrance Exams", icon: Award },
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
      { href: "/dashboard/modules/school/clubs", label: "Clubs & Activities", icon: Users2 },
      { href: "/dashboard/modules/school/journals", label: "Photo Journals", icon: Camera },
      { href: "/dashboard/modules/school/remarks", label: "Weekly Remarks", icon: MessageCircle },
      { href: "/dashboard/modules/school/feedback", label: "Feedback", icon: MessageSquare },
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
    label: "People & HR",
    icon: Briefcase,
    items: [
      { href: "/dashboard/modules/school/teachers", label: "Teachers", icon: UserCheck },
      { href: "/dashboard/modules/school/staff", label: "Staff", icon: UsersIcon },
      { href: "/dashboard/modules/school/ratings", label: "Teacher Ratings", icon: Star },
      // Batch 1 (People & HR) — shipped. Permission resolved from the access map:
      // parents → school:parents:read; the two HR surfaces → hr:write.
      { href: "/dashboard/modules/school/parents", label: "Parents Directory", icon: Contact },
      { href: "/dashboard/modules/school/staff-assessment", label: "Staff Assessment", icon: ClipboardList },
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
      { href: "/dashboard/modules/school/facility", label: "Facility Management", icon: Building2 },
      { href: "/dashboard/modules/school/visitor", label: "Visitor Management", icon: UserCheck },
    ],
  },
  {
    // Educare "Admin Management". Audit Trail surfaces the existing Core Audit Log
    // here (same route, grouped like Educare). Biometric + Custom Field reuse the
    // platform pages. Still deferred (new backend): Week Entries, Result Publish
    // Helper, Manage User Roles & Password.
    key: "admin-management",
    requiredModule: "school",
    label: "Admin Management",
    icon: Shield,
    items: [
      { href: "/dashboard/audit", label: "Audit Trail", icon: FileText },
      { href: "/dashboard/modules/school/deactivated-users", label: "Manage Deactivated Users", icon: UserCog },
      { href: "/dashboard/modules/school/week-entries", label: "Manage Week Entries", icon: CalendarClock },
      { href: "/dashboard/modules/school/result-publish", label: "Result Publish Helper", icon: ClipboardList },
      // Role management lives on the Users page (the one source of truth); the old
      // "Manage User Roles & Password" surface was a duplicate and now redirects there.
      { href: "/dashboard/modules/school/biometric", label: "Manage Biometric", icon: Activity },
      { href: "/dashboard/modules/school/custom-fields", label: "Manage Custom Field", icon: FolderOpen },
    ],
  },
  {
    key: "administration",
    requiredModule: "school",
    label: "Administration",
    icon: Settings,
    items: [
      // Batch 7 (Administration & Platform) — shipped. All settings:read gated.
      { href: "/dashboard/modules/school/school-setup", label: "School Setup", icon: Settings },
      { href: "/dashboard/modules/school/voting", label: "Voting System", icon: Gavel },
      { href: "/dashboard/modules/school/mailbox", label: "Mailbox", icon: MessageSquare },
      { href: "/dashboard/modules/school/mobile", label: "Mobile Manager", icon: MonitorCheck },
    ],
  },
  // Hospital & Business workspaces are retired for the Fairview School Portal.
  // Only the school workspace is surfaced. (Backend deprecation strategy is
  // unchanged — those routes are simply no longer mounted or navigated to.)
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, org, activeRole, hasPermission } = useAuthStore();
  const logout = useLogout();
  const roleScope = moduleAllowedForOrg(org, "school") ? activeRole : "admin";

  // The backend returns workspace-filtered modules. We still evaluate the
  // industry locally so stale persisted state cannot flash another product
  // shell while /me is hydrating.
  // If the org hasn't hydrated yet, render nothing module-side to avoid
  // a flash of the wrong product shell.
  const enabled = org ? effectiveModulesForOrg(org) : undefined;

  const isActive = useCallback(
    (href: string) =>
      pathname === href || (href !== "/dashboard" && pathname.startsWith(href)),
    [pathname],
  );

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
    <aside className="no-print fixed left-0 top-0 h-screen w-64 bg-white border-r border-slate-200/70 flex flex-col z-30 shadow-sm">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-100">
        <BrandMark className="h-8 shrink-0" priority />
        <div className="min-w-0">
          <p className="text-sm font-black text-slate-900 truncate">{org?.name || "Fairview School Portal"}</p>
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 truncate">
            School Portal
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {/* Core */}
        <div>
          <p className="px-3 mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">Core</p>
          <div className="space-y-0.5">
            {visibleCoreNav.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => markNavClick(href)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all",
                  isActive(href)
                    ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                )}
              >
                <Icon size={16} />
                {label}
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
            pathname={pathname}
            isActive={isActive}
          />
        ))}
      </nav>

      {/* Bottom */}
      <div className="px-3 pb-4 pt-2 border-t border-slate-100 space-y-0.5">
        <Link
          href="/dashboard/profile"
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all",
            isActive("/dashboard/profile")
              ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
              : "text-slate-600 hover:bg-slate-100"
          )}
        >
          <User size={16} />
          Profile
        </Link>
        {hasPermission("settings:read") && (
          <Link
            href="/dashboard/settings"
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all",
              isActive("/dashboard/settings")
                ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
                : "text-slate-600 hover:bg-slate-100"
            )}
          >
            <Settings size={16} />
            Settings
          </Link>
        )}
        <Link
          href="/support"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition-all"
        >
          <HelpCircle size={16} />
          Support
        </Link>
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-red-500 hover:bg-red-50 transition-all w-full text-left"
        >
          <LogOut size={16} />
          Sign out
        </button>

        {/* User card */}
        {user && (
          <Link href="/dashboard/profile" className="block mt-3">
            <div className="px-3 py-2.5 rounded-lg bg-slate-50 border border-slate-100 hover:bg-slate-100 transition-colors">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center text-white text-xs font-bold shrink-0 overflow-hidden">
                  {user.avatar_url ? (
                    <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    user.full_name.charAt(0)
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-slate-800 truncate">{user.full_name}</p>
                  <p className="text-[10px] text-slate-400 truncate">{user.email}</p>
                </div>
              </div>
            </div>
          </Link>
        )}
      </div>
    </aside>
  );
}

function ModuleSectionsSkeleton() {
  return (
    <div className="space-y-5" aria-hidden>
      {[0, 1].map((i) => (
        <div key={i}>
          <div className="px-3 mb-2 h-3 w-20 bg-slate-100 rounded animate-pulse" />
          <div className="space-y-1">
            {[0, 1, 2, 3].map((j) => (
              <div key={j} className="h-8 mx-1 bg-slate-50 rounded-lg animate-pulse" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

const CollapsibleSection = memo(function CollapsibleSection({
  section,
  pathname,
  isActive,
}: {
  section: ModuleSection;
  pathname: string;
  isActive: (href: string) => boolean;
}) {
  // Sections render EXPANDED by default so an admin sees the whole menu at a
  // glance (EduCare-style). Users can still collapse any section via the header.
  const [open, setOpen] = useState(true);
  const ModuleIcon = section.icon;

  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 mb-1 w-full group"
      >
        <ModuleIcon size={12} className="text-slate-400" />
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 flex-1 text-left">
          {section.label}
        </p>
        <ChevronDown
          size={12}
          className={cn(
            "text-slate-400 transition-transform duration-200",
            !open && "-rotate-90"
          )}
        />
      </button>
      {open && (
        <div className="space-y-0.5 animate-fade-in">
          {section.items.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => markNavClick(href)}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all",
                isActive(href)
                  ? "bg-brand-50 text-brand-700 border border-brand-200"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              )}
            >
              <Icon size={15} />
              {label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
});
