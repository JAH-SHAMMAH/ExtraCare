"use client";

import Link from "next/link";
import { useFacilityReport } from "@/hooks/useFacility";
import { ArrowLeft, Loader2, Building2, MessageSquareWarning, Wrench, Receipt } from "lucide-react";

export default function FacilityReportPage() {
  const { data, isLoading } = useFacilityReport();
  const cards = [
    { label: "Facilities", value: data?.cards.facilities ?? 0, icon: Building2, tone: "text-sky-600 bg-sky-50" },
    { label: "Complaints", value: data?.cards.complaints ?? 0, icon: MessageSquareWarning, tone: "text-amber-600 bg-amber-50" },
    { label: "Maintenance", value: data?.cards.maintenance ?? 0, icon: Wrench, tone: "text-indigo-600 bg-indigo-50" },
    { label: "Approved Requisitions", value: data?.cards.approved_requisitions ?? 0, icon: Receipt, tone: "text-emerald-600 bg-emerald-50" },
  ];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/facility" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Facility Management</Link>
      <div className="mb-6"><nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Facility Management</span><span>/</span><span className="text-brand-600 font-semibold">Report</span></nav><h1 className="text-2xl font-black text-slate-900 tracking-tight">Facility Report</h1></div>

      {isLoading ? <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div> : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {cards.map((c) => (<div key={c.label} className="bg-white rounded-xl border border-slate-200 p-5"><div className={`w-9 h-9 rounded-lg flex items-center justify-center mb-3 ${c.tone}`}><c.icon size={18} /></div><p className="text-2xl font-black text-slate-900 tabular-nums">{c.value}</p><p className="text-xs text-slate-500 mt-0.5">{c.label}</p></div>))}
          </div>
          <p className="text-xs text-slate-500 mb-6">{data?.pending_complaints ?? 0} pending complaint(s).</p>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h2 className="text-sm font-bold text-slate-800 mb-3">Facilities by type</h2>
              {(data?.by_type ?? []).length === 0 ? <p className="text-sm text-slate-400">No data yet.</p> : (
                <div className="space-y-2">{data!.by_type.map((t) => { const max = Math.max(...data!.by_type.map((x) => x.count), 1); return (
                  <div key={t.name} className="flex items-center gap-2"><span className="text-xs text-slate-600 w-28 truncate">{t.name}</span><div className="flex-1 h-4 bg-slate-100 rounded"><div className="h-4 bg-brand-500 rounded" style={{ width: `${(t.count / max) * 100}%` }} /></div><span className="text-xs text-slate-500 tabular-nums w-6 text-right">{t.count}</span></div>
                ); })}</div>
              )}
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h2 className="text-sm font-bold text-slate-800 mb-3">Expenses by approval level</h2>
              {(data?.expenses_by_level ?? []).length === 0 ? <p className="text-sm text-slate-400">No data yet.</p> : (
                <table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-100">{["Level", "Total", "Approved"].map((h) => <th key={h} className="pb-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-slate-50">{data!.expenses_by_level.map((e) => (<tr key={e.level}><td className="py-2 text-slate-700">{e.level}</td><td className="py-2 tabular-nums text-slate-600">{e.total.toLocaleString()}</td><td className="py-2 tabular-nums text-emerald-600">{e.approved.toLocaleString()}</td></tr>))}</tbody></table>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
