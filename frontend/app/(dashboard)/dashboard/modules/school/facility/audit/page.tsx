"use client";

import { useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useFacilityAudit } from "@/hooks/useFacility";
import { ArrowLeft, Loader2, History } from "lucide-react";

type Cat = "facility" | "complaints" | "inspection" | "maintenance" | "requisition";
const TABS: [Cat, string][] = [["facility", "Facility List"], ["complaints", "Complaints"], ["inspection", "Inspection"], ["maintenance", "Maintenance"], ["requisition", "Requisition"]];

export default function FacilityAuditPage() {
  const [cat, setCat] = useState<Cat>("facility");
  const { data, isLoading } = useFacilityAudit(cat);
  const rows = data?.items || [];
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/facility" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Facility Management</Link>
      <div className="mb-5"><nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Facility Management</span><span>/</span><span className="text-brand-600 font-semibold">Audit Trail</span></nav><h1 className="text-2xl font-black text-slate-900 tracking-tight">Audit Trail</h1><p className="text-slate-500 text-sm mt-0.5">A filtered view of the school-wide audit log for facility activity.</p></div>
      <div className="flex gap-1 border-b border-slate-200 mb-6 flex-wrap">{TABS.map(([k, l]) => (<button key={k} onClick={() => setCat(k)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", cat === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>))}</div>
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <div className="py-16 text-center text-slate-400 text-sm"><History size={30} className="mx-auto mb-2 opacity-50" />No activity yet.</div>
          : (<table className="w-full text-left"><thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Full Name", "Activity", "Date"].map((h) => (<th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">{rows.map((a) => (<tr key={a.id} className="hover:bg-slate-50/70">
              <td className="px-5 py-3 text-sm font-semibold text-slate-800">{a.full_name || "—"}</td>
              <td className="px-5 py-3 text-sm text-slate-600">{a.activity || "—"}</td>
              <td className="px-5 py-3 text-xs text-slate-400">{a.date ? new Date(a.date).toLocaleString() : "—"}</td>
            </tr>))}</tbody></table>)}
      </div>
    </div>
  );
}
