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
  CalendarClock, Gavel, Newspaper, Radio, Library, Bus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore, type ActiveRole } from "@/lib/store";
import { effectiveModulesForOrg, moduleAllowedForOrg } from "@/lib/workspace";
import { useLogout } from "@/hooks/useAuth";
import { markNavClick } from "@/lib/perf";

const CORE_NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  // Phase 6.3 role-specific shortcuts. The sidebar filter hides these unless
  // the active role matches — a student only ever sees "My Timetable", a
  // parent only ever sees "My Children", a teacher sees "My Classes".
  { href: "/dashboard/my-children", label: "My Children", icon: UserCircle, roleOnly: "parent" as ActiveRole },
  { href: "/dashboard/my-children/attendance", label: "Attendance", icon: ClipboardList, roleOnly: "parent" as ActiveRole },
  { href: "/dashboard/my-timetable", label: "My Timetable", icon: Calendar, roleOnly: "student" as ActiveRole },
  { href: "/dashboard/my-library", label: "My Library", icon: Library, roleOnly: "student" as ActiveRole },
  { href: "/dashboard/my-classes", label: "My Classes", icon: School, roleOnly: "teacher" as ActiveRole },
  { href: "/dashboard/my-classes/attendance", label: "Class Attendance", icon: ClipboardList, roleOnly: "teacher" as ActiveRole },
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


// Phase 6.3 sidebar visibility by active role. `admin` sees everything (no
// filter applied). Non-admin roles get an explicit allow-list keyed by href —
// simpler than tagging every item and easier to audit at a glance.
//
// When a new page is added, update the allow-list for every role that should
// see it (or leave it admin-only).
const ROLE_ALLOWED_HREFS: Record<Exclude<ActiveRole, "admin">, Set<string>> = {
  teacher: new Set([
    "/dashboard",
    "/dashboard/my-classes",
    "/dashboard/profile",
    "/dashboard/notifications",
    "/dashboard/hrm/my-info",
    "/dashboard/hrm/leave",
    "/messenger",
    "/news-feed",
    "/dashboard/modules/school/students",
    "/dashboard/modules/school/classes",
    "/dashboard/modules/school/subjects",
    "/dashboard/modules/school/attendance",
    "/dashboard/modules/school/exams",
    "/dashboard/modules/school/grades",
    "/dashboard/modules/school/timetable",
    "/dashboard/modules/school/lessons",
    "/dashboard/modules/school/eclassroom",
    "/dashboard/modules/school/cbt",
    "/dashboard/modules/school/cbt/live",
    "/dashboard/modules/school/behaviour",
    "/dashboard/modules/school/feedback",
    "/dashboard/modules/school/remarks",
    "/dashboard/modules/school/journals",
    "/dashboard/modules/school/clubs",
    "/dashboard/modules/school/report-cards",
    "/dashboard/modules/school/library",
  ]),
  student: new Set([
    "/dashboard",
    "/dashboard/my-timetable",
    "/dashboard/my-library",
    "/dashboard/profile",
    "/dashboard/notifications",
    "/messenger",
    "/news-feed",
    "/dashboard/modules/school/eclassroom",
    "/dashboard/modules/school/cbt",
    "/dashboard/modules/school/clubs",
    "/dashboard/modules/school/journals",
    "/dashboard/modules/school/grades",
    "/dashboard/modules/school/lessons",
  ]),
  parent: new Set([
    "/dashboard",
    "/dashboard/my-children",
    "/dashboard/profile",
    "/dashboard/notifications",
    "/messenger",
    "/news-feed",
    "/dashboard/modules/school/attendance",
    "/dashboard/modules/school/grades",
    "/dashboard/modules/school/fees",
    "/dashboard/modules/school/payments",
    "/dashboard/modules/school/report-cards",
    "/dashboard/modules/school/feedback",
    "/dashboard/modules/school/journals",
  ]),
};


function isAllowedForRole(href: string, activeRole: ActiveRole | null): boolean {
  // No active role yet → render admin view. Prevents a flash of "empty
  // sidebar" while /me/contexts resolves on first page load.
  if (!activeRole || activeRole === "admin") return true;
  return ROLE_ALLOWED_HREFS[activeRole].has(href);
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

const MODULE_SECTIONS: ModuleSection[] = [
  {
    key: "school",
    requiredModule: "school",
    label: "Education",
    icon: GraduationCap,
    items: [
      { href: "/dashboard/modules/school/students", label: "Students", icon: Users2 },
      { href: "/dashboard/modules/school/teachers", label: "Teachers", icon: UserCheck },
      { href: "/dashboard/modules/school/staff", label: "Staff", icon: UsersIcon },
      { href: "/dashboard/modules/school/classes", label: "Classes", icon: School },
      { href: "/dashboard/modules/school/subjects", label: "Subjects", icon: BookMarked },
      { href: "/dashboard/modules/school/attendance", label: "Attendance", icon: ClipboardList },
      { href: "/dashboard/modules/school/attendance/dashboard", label: "Attendance Insights", icon: BarChart3 },
      { href: "/dashboard/modules/school/exams", label: "Exams & Results", icon: Award },
      { href: "/dashboard/modules/school/grades", label: "Gradebook", icon: BookOpen },
      { href: "/dashboard/modules/school/timetable", label: "Timetable", icon: Calendar },
      { href: "/dashboard/modules/school/lessons", label: "Lesson Planner", icon: NotebookPen },
      { href: "/dashboard/modules/school/library", label: "Library", icon: Library },
      { href: "/dashboard/modules/school/sms", label: "Bulk SMS", icon: MessageSquare },
      { href: "/dashboard/modules/school/transport", label: "Transport", icon: Bus },
      { href: "/dashboard/modules/school/report-cards", label: "Report Cards", icon: FileText },
      { href: "/dashboard/modules/school/fees", label: "Fee Management", icon: Wallet },
      { href: "/dashboard/modules/school/ratings", label: "Teacher Ratings", icon: Star },
      { href: "/dashboard/modules/school/eclassroom", label: "eClassroom", icon: NotebookPen },
      { href: "/dashboard/modules/school/cbt", label: "CBT", icon: MonitorCheck },
      { href: "/dashboard/modules/school/cbt/live", label: "Live Classes", icon: Radio },
      { href: "/dashboard/modules/school/behaviour", label: "Pastoral Care", icon: HeartHandshake },
      { href: "/dashboard/modules/school/feedback", label: "Feedback", icon: MessageSquare },
      { href: "/dashboard/modules/school/clubs", label: "Clubs & Activities", icon: Users2 },
      { href: "/dashboard/modules/school/journals", label: "Photo Journals", icon: Camera },
      { href: "/dashboard/modules/school/remarks", label: "Weekly Remarks", icon: MessageCircle },
      { href: "/dashboard/modules/school/tuckshop", label: "Tuckshop", icon: ShoppingCart },
    ],
  },
  // Hospital & Business workspaces are retired for the Fairview School Portal.
  // Only the school workspace is surfaced. (Backend deprecation strategy is
  // unchanged — those routes are simply no longer mounted or navigated to.)
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, org, activeRole } = useAuthStore();
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

  // Phase 6.3: build the visible core-nav list once, filtered by active role.
  // `roleOnly` items only render when their active role matches; everything
  // else goes through the allow-list in isAllowedForRole.
  const visibleCoreNav = useMemo(
    () => CORE_NAV.filter((item) => {
      if ((item as { roleOnly?: ActiveRole }).roleOnly) {
        const only = (item as { roleOnly?: ActiveRole }).roleOnly;
        return roleScope === only;
      }
      return isAllowedForRole(item.href, roleScope ?? null);
    }),
    [roleScope],
  );

  // Pre-filter module sections by module AND by active role. For non-admin
  // roles we also drop any item whose href is not in the role's allow-list —
  // a teacher's "Education" section should only show teaching-relevant items,
  // not "Teacher Ratings" or "Fee Management".
  const visibleSections = useMemo(() => {
    if (!enabled) return [] as ModuleSection[];
    return MODULE_SECTIONS
      .filter((s) => moduleAllowedForOrg(org, s.requiredModule as "school" | "business" | "hospital"))
      .map((s) => ({
        ...s,
        items: s.items.filter((it) => isAllowedForRole(it.href, roleScope ?? null)),
      }))
      .filter((s) => s.items.length > 0);
  }, [enabled, org, roleScope]);

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-white border-r border-slate-200/70 flex flex-col z-30 shadow-sm">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-100">
        <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center shrink-0">
          <Building2 size={16} className="text-white" />
        </div>
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
  // `hasActiveChild` is recomputed only when pathname changes. useMemo keeps
  // the 20-item .some() out of every parent render.
  const hasActiveChild = useMemo(
    () => section.items.some((item) => isActive(item.href)),
    [section.items, isActive],
  );
  const [open, setOpen] = useState(hasActiveChild);
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
