"use client";

import { useHeadDashboard } from "@/hooks/usePastoral";
import { cn } from "@/lib/utils";
import { Loader2, LayoutDashboard, BedDouble, Users2, Home, Plane, Gavel, Award, UserCog } from "lucide-react";
import Link from "next/link";

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  dismissed: "bg-slate-50 text-slate-500 border-slate-200",
};

export default function PastoralDashboardPage() {
  const { data, isLoading } = useHeadDashboard();

  const kpis = [
    { label: "Boarders", value: data?.boarders, icon: Users2, href: "/dashboard/modules/school/hostel-students" },
    { label: "Hostels", value: data?.hostels, icon: BedDouble, href: "/dashboard/modules/school/hostel" },
    { label: "Houses", value: data?.houses, icon: Home, href: "/dashboard/modules/school/pastoral-students" },
    { label: "Pending Exeats", value: data?.pending_exeats, icon: Plane, href: "/dashboard/modules/school/exeat" },
    { label: "Open Cases", value: data?.open_cases, icon: Gavel, href: "/dashboard/modules/school/behaviour-sanction" },
    { label: "Leadership Roles", value: data?.leadership_roles, icon: Award, href: "/dashboard/modules/school/pastoral-setup" },
  ];

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Pastoral Dashboard</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><LayoutDashboard size={22} className="text-brand-600" /> Pastoral Dashboard</h1>
      <p className="text-slate-500 text-sm mb-6">An at-a-glance view for the pastoral head: boarding, welfare and discipline.</p>

      {isLoading ? (
        <div className="py-20 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-slate-400" /></div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
            {kpis.map((k) => (
              <Link key={k.label} href={k.href} className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md hover:border-brand-200 transition">
                <k.icon size={18} className="text-brand-500 mb-2" />
                <p className="text-2xl font-black text-slate-900 tabular-nums">{k.value ?? 0}</p>
                <p className="text-xs text-slate-500 mt-0.5">{k.label}</p>
              </Link>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2"><UserCog size={16} className="text-slate-400" /><h2 className="text-sm font-bold text-slate-800">Pastoral Heads</h2></div>
              {(data?.heads ?? []).length === 0 ? (
                <p className="text-sm text-slate-400 py-8 text-center">No pastoral heads assigned.</p>
              ) : (
                <ul className="divide-y divide-slate-50">
                  {(data?.heads ?? []).map((h: any) => (
                    <li key={h.id} className="px-5 py-3 flex items-center justify-between">
                      <span className="text-sm font-semibold text-slate-800">{h.user_name || h.user_id.slice(0, 8)}</span>
                      <span className="text-xs text-slate-500">{h.title}{h.scope ? ` · ${h.scope}` : ""}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2"><Gavel size={16} className="text-slate-400" /><h2 className="text-sm font-bold text-slate-800">Recent Disciplinary Cases</h2></div>
              {(data?.recent_cases ?? []).length === 0 ? (
                <p className="text-sm text-slate-400 py-8 text-center">No cases logged.</p>
              ) : (
                <ul className="divide-y divide-slate-50">
                  {(data?.recent_cases ?? []).map((c: any) => (
                    <li key={c.id} className="px-5 py-3 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-800 truncate">{c.student_name}</p>
                        <p className="text-xs text-slate-400 truncate">{[c.action_name, c.case_date].filter(Boolean).join(" · ") || "—"}</p>
                      </div>
                      <span className={cn("badge capitalize shrink-0", STATUS_STYLE[c.status] || STATUS_STYLE.dismissed)}>{c.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
