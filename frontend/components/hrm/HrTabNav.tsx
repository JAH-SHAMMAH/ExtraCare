"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home, Settings2, Users2, UserCircle, CalendarClock, GraduationCap,
  Star, AlertTriangle, Fingerprint, Briefcase, ChevronDown, Lock,
} from "lucide-react";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";

/**
 * HR Manager top navigation (Educare parity). A plain row of tab labels; clicking
 * a tab accordion-expands ONLY that tab's sub-items below the row (one open at a
 * time), matching Educare's click-to-expand behaviour rather than an always-open
 * mega menu.
 *
 * RBAC: each item declares the permission it needs. Regular staff (hr:read) see
 * only their self-service items (My Info, My Leave, …); HR/admin (hr:write) see
 * everything. Net-new pages not built yet are shown DISABLED to admins (so the
 * full Educare structure is visible as a roadmap) and hidden from staff. Direct
 * page access is separately blocked by RouteGuard + access.ts.
 */

type Item = { label: string; href?: string; perm: Perm; built?: boolean };
type Perm = "hr:read" | "hr:write";
type Tab = { key: string; label: string; icon: any; href?: string; perm: Perm; items?: Item[] };

const W: Perm = "hr:write";
const R: Perm = "hr:read";

const TABS: Tab[] = [
  { key: "home", label: "Home", icon: Home, href: "/dashboard/hrm", perm: W },
  {
    key: "admin", label: "Admin", icon: Settings2, perm: W, items: [
      { label: "Job Titles", perm: W }, { label: "Job Categories", perm: W },
      { label: "Pay Grades", perm: W }, { label: "Salary Components", perm: W },
      { label: "Work Shifts", perm: W }, { label: "Employment Status", perm: W },
      { label: "Working Tools", perm: W }, { label: "Organization Structure", perm: W },
      { label: "Competency List", perm: W }, { label: "Qualification — Skills", perm: W },
      { label: "Qualification — Education", perm: W }, { label: "Qualification — Licenses", perm: W },
      { label: "Qualification — Languages", perm: W }, { label: "Qualification — Memberships", perm: W },
      { label: "Staff Confirmation", perm: W }, { label: "HR Departments", perm: W },
      { label: "HR Operations", perm: W }, { label: "Pension Fund Administrators", perm: W },
      { label: "Contributory Leave Allowance", perm: W }, { label: "Documents", perm: W },
    ],
  },
  {
    key: "pim", label: "PIM", icon: Users2, perm: W, items: [
      { label: "Employee List", href: "/dashboard/modules/school/staff", perm: W, built: true },
      { label: "Staff Transfer Log", perm: W }, { label: "Staff Account Numbers", perm: W },
      { label: "Staff Confirmation List", perm: W }, { label: "Configuration", perm: W },
    ],
  },
  { key: "my-info", label: "My Info", icon: UserCircle, href: "/dashboard/hrm/my-info", perm: R },
  {
    key: "leave", label: "Leave", icon: CalendarClock, perm: R, items: [
      { label: "Apply", href: "/dashboard/hrm/leave", perm: R, built: true },
      { label: "My Leave", href: "/dashboard/hrm/leave", perm: R, built: true },
      { label: "Leave List", href: "/dashboard/hrm/leave/admin", perm: W, built: true },
      { label: "Reports", href: "/dashboard/hrm/leave/admin", perm: W, built: true },
      { label: "Entitlements", perm: R }, { label: "Assign Leave", perm: W }, { label: "Configure", perm: W },
    ],
  },
  {
    key: "training", label: "Training", icon: GraduationCap, perm: W, items: [
      { label: "Trainings", perm: W }, { label: "Sessions", perm: W }, { label: "Configuration", perm: W },
    ],
  },
  {
    key: "performance", label: "Performance", icon: Star, perm: W, items: [
      { label: "Appraisals", href: "/dashboard/hrm/performance", perm: W, built: true },
      { label: "Appraisal Configuration", perm: W }, { label: "Competency Mappings", perm: W },
    ],
  },
  {
    key: "discipline", label: "Discipline", icon: AlertTriangle, perm: R, items: [
      { label: "Disciplinary Cases", href: "/dashboard/hrm/disciplinary", perm: W, built: true },
      { label: "My Actions", perm: R }, { label: "Disciplinary Types", perm: W },
    ],
  },
  {
    key: "access", label: "Access Control", icon: Fingerprint, perm: R, items: [
      { label: "Clock in / Clock out Log", perm: W }, { label: "My Attendance Record", perm: R },
      { label: "Configuration", perm: W },
    ],
  },
  {
    key: "recruitment", label: "Recruitment", icon: Briefcase, perm: W, items: [
      { label: "Vacancies", href: "/dashboard/hrm/recruitment", perm: W, built: true },
      { label: "Configuration", perm: W },
    ],
  },
];

export function HrTabNav() {
  const pathname = usePathname();
  const canWrite = useHasPermission("hr:write");
  const canRead = useHasPermission("hr:read");
  const has = (p: Perm) => (p === "hr:write" ? canWrite : canRead || canWrite);
  const [open, setOpen] = useState<string | null>(null);

  // An item is visible if the user has its permission AND it's built (or the
  // user is HR/admin, who also sees not-yet-built items as a disabled roadmap).
  const visibleItems = (t: Tab) => (t.items ?? []).filter((it) => has(it.perm) && (it.built || canWrite));
  const tabVisible = (t: Tab) => (t.href ? has(t.perm) : visibleItems(t).length > 0);

  const tabs = TABS.filter(tabVisible);
  if (tabs.length === 0) return null;

  const isActive = (t: Tab) => {
    if (t.href) return pathname === t.href;
    return (t.items ?? []).some((it) => it.href && pathname.startsWith(it.href));
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl mb-6 overflow-hidden">
      {/* Tab label row */}
      <div className="flex flex-wrap items-center gap-1 px-2 py-1.5 border-b border-slate-100">
        {tabs.map((t) => {
          const active = isActive(t);
          const expandable = !t.href;
          const content = (
            <>
              <t.icon size={14} />
              <span>{t.label}</span>
              {expandable && <ChevronDown size={13} className={cn("transition-transform", open === t.key && "rotate-180")} />}
            </>
          );
          const classes = cn(
            "flex items-center gap-1.5 px-3 py-2 text-sm font-semibold rounded-lg transition-colors",
            active ? "text-brand-700 bg-brand-50" : "text-slate-600 hover:bg-slate-100",
          );
          return t.href ? (
            <Link key={t.key} href={t.href} className={classes} onClick={() => setOpen(null)}>{content}</Link>
          ) : (
            <button key={t.key} onClick={() => setOpen(open === t.key ? null : t.key)} className={classes}>{content}</button>
          );
        })}
      </div>

      {/* Expanded panel — only the clicked tab's sub-items */}
      {open && (() => {
        const t = tabs.find((x) => x.key === open);
        const items = t ? visibleItems(t) : [];
        if (!t || items.length === 0) return null;
        return (
          <div className="px-3 py-3 bg-slate-50/60">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">{t.label}</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
              {items.map((it) => it.built && it.href ? (
                <Link key={it.label} href={it.href} onClick={() => setOpen(null)}
                  className={cn("text-sm px-3 py-2 rounded-lg border transition-colors",
                    it.href && pathname.startsWith(it.href) ? "border-brand-300 bg-brand-50 text-brand-700 font-semibold" : "border-slate-200 bg-white text-slate-700 hover:border-brand-300 hover:text-brand-700")}>
                  {it.label}
                </Link>
              ) : (
                <span key={it.label} title="Coming in a later phase" className="flex items-center justify-between gap-1 text-sm px-3 py-2 rounded-lg border border-dashed border-slate-200 bg-white/50 text-slate-400 cursor-default">
                  {it.label} <Lock size={11} />
                </span>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
