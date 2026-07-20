"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ChevronDown, Lock } from "lucide-react";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { HR_TABS, type HrTab, type HrPerm } from "./hrNav";

/**
 * HR Manager top navigation (Educare parity). A plain row of tab labels; clicking
 * a tab accordion-expands ONLY that tab's sub-items below the row (one at a time).
 * A ?open=<tabKey> query param (used by the dashboard Quick Links) pre-expands that
 * tab on arrival, so landing from a Quick Link shows the section already open.
 *
 * RBAC: staff (hr:read) see only self-service items; HR/admin (hr:write) see all.
 * Net-new pages show DISABLED to admins as a roadmap and are hidden from staff.
 * Hidden entirely on the HR landing (/dashboard/hrm) — Quick Links live there.
 */
export function HrTabNav() {
  const pathname = usePathname();
  const params = useSearchParams();
  const openParam = params.get("open");
  const canWrite = useHasPermission("hr:write");
  const canRead = useHasPermission("hr:read");
  const has = (p: HrPerm) => (p === "hr:write" ? canWrite : canRead || canWrite);
  const [open, setOpen] = useState<string | null>(openParam);

  // Re-sync the expanded tab when arriving with a new ?open (layout persists
  // across /hrm navigations, so useState alone wouldn't pick up the change).
  useEffect(() => { if (openParam) setOpen(openParam); }, [openParam]);

  const visibleItems = (t: HrTab) => (t.items ?? []).filter((it) => has(it.perm) && (it.built || canWrite));
  const tabVisible = (t: HrTab) => (t.href ? has(t.perm) : visibleItems(t).length > 0);

  // Educare shows only the Quick Links on the HR landing page — the tab bar
  // appears once you're inside a specific HR section, never on the dashboard.
  if (pathname === "/dashboard/hrm") return null;

  const tabs = HR_TABS.filter(tabVisible);
  if (tabs.length === 0) return null;

  const isActive = (t: HrTab) => {
    if (t.href) return pathname === t.href;
    return (t.items ?? []).some((it) => it.href && pathname.startsWith(it.href));
  };

  return (
    <div className="px-8 pt-8 max-w-6xl mx-auto w-full">
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

        {/* Expanded panel — only the clicked (or ?open) tab's sub-items */}
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
    </div>
  );
}
