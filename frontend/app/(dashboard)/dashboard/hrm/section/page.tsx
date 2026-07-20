"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Lock } from "lucide-react";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { HR_TABS, type HrPerm } from "@/components/hrm/hrNav";

/**
 * HR section landing — the page a dashboard Quick Link lands on. The tab bar
 * (rendered by the /hrm layout) pre-expands this section via ?open; here we show
 * the section's sub-items as cards so the user immediately sees what's available.
 */
export default function HrSectionPage() {
  const params = useSearchParams();
  const key = params.get("open") || "admin";
  const canWrite = useHasPermission("hr:write");
  const canRead = useHasPermission("hr:read");
  const has = (p: HrPerm) => (p === "hr:write" ? canWrite : canRead || canWrite);

  const tab = HR_TABS.find((t) => t.key === key);
  const items = (tab?.items ?? []).filter((it) => has(it.perm) && (it.built || canWrite));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">{tab?.label ?? "Section"}</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">{tab?.label ?? "HR Manager"}</h1>
        <p className="text-slate-500 text-sm mt-0.5">Choose an option below, or use the tabs above to jump to another section.</p>
      </div>

      {items.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-400">Nothing available in this section for your role.</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {items.map((it) => it.built && it.href ? (
            <Link key={it.label} href={it.href}
              className="group bg-white rounded-xl border border-slate-200 p-4 flex items-center justify-between hover:shadow-md hover:border-brand-300 transition-all">
              <span className="text-sm font-semibold text-slate-800 group-hover:text-brand-700">{it.label}</span>
              <ArrowRight size={15} className="text-slate-300 group-hover:text-brand-500" />
            </Link>
          ) : (
            <div key={it.label} title="Coming in a later phase"
              className="bg-white/60 rounded-xl border border-dashed border-slate-200 p-4 flex items-center justify-between text-slate-400 cursor-default">
              <span className="text-sm font-medium">{it.label}</span>
              <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide"><Lock size={11} /> Soon</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
