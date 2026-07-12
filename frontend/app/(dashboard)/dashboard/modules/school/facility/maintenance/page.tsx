"use client";

import { useState } from "react";
import Link from "next/link";
import { cn, formatDate } from "@/lib/utils";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { useFacilityMaintenance, useSaveMaintenance, useFacilities, useFacilityComplaints } from "@/hooks/useFacility";
import { ArrowLeft, Plus, X, Loader2, Wrench } from "lucide-react";
import type { FacilityMaintenanceItem } from "@/types";

const STATUSES = ["pending", "approved", "in_progress", "completed", "rejected"];
const STATUS_STYLE: Record<string, string> = { pending: "bg-amber-50 text-amber-700 border-amber-200", approved: "bg-blue-50 text-blue-700 border-blue-200", in_progress: "bg-indigo-50 text-indigo-700 border-indigo-200", completed: "bg-emerald-50 text-emerald-700 border-emerald-200", rejected: "bg-rose-50 text-rose-700 border-rose-200" };

export default function FacilityMaintenancePage() {
  const canWrite = useHasPermission("school_admin:facility:write");
  const [mine, setMine] = useState(true);
  const { data, isLoading } = useFacilityMaintenance(mine);
  const { data: facilities } = useFacilities();
  const { data: complaints } = useFacilityComplaints(false);
  const save = useSaveMaintenance();
  const rows: FacilityMaintenanceItem[] = data || [];
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ facility_id: "", complaint_id: "", maintenance_type: "", comment: "", total_cost: "0" });
  const reset = () => { setForm({ facility_id: "", complaint_id: "", maintenance_type: "", comment: "", total_cost: "0" }); setShow(false); };
  const submit = () => save.mutate({ data: { facility_id: form.facility_id || null, complaint_id: form.complaint_id || null, maintenance_type: form.maintenance_type || null, comment: form.comment || null, total_cost: Number(form.total_cost) || 0 } }, { onSuccess: reset });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/facility" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Facility Management</Link>
      <div className="flex items-end justify-between mb-4 gap-4">
        <div><nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Facility Management</span><span>/</span><span className="text-brand-600 font-semibold">Maintenance</span></nav><h1 className="text-2xl font-black text-slate-900 tracking-tight">Facility Maintenance</h1></div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> Request Maintenance</button>}
      </div>
      <div className="flex bg-slate-100 rounded-lg p-0.5 w-fit mb-4"><button onClick={() => setMine(true)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", mine ? "bg-white shadow" : "text-slate-600")}>My Requests</button><button onClick={() => setMine(false)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", !mine ? "bg-white shadow" : "text-slate-600")}>All Requests</button></div>
      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Request maintenance</h2><button onClick={reset}><X size={18} className="text-slate-400" /></button></div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Facility <span className="text-slate-400 font-normal">(optional)</span></label><select value={form.facility_id} onChange={(e) => setForm({ ...form, facility_id: e.target.value })} className="input"><option value="">— None —</option>{(facilities || []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></div>
            <div><label className="label">Complaint (optional)</label><select value={form.complaint_id} onChange={(e) => setForm({ ...form, complaint_id: e.target.value })} className="input"><option value="">—</option>{(complaints || []).map((c) => <option key={c.id} value={c.id}>{c.reference} · {c.title}</option>)}</select></div>
            <div><label className="label">Maintenance type</label><input value={form.maintenance_type} onChange={(e) => setForm({ ...form, maintenance_type: e.target.value })} className="input" placeholder="repair, preventive…" /></div>
            <div><label className="label">Estimated cost</label><input type="number" value={form.total_cost} onChange={(e) => setForm({ ...form, total_cost: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Comment</label><textarea value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Submit</button></div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <div className="py-16 text-center text-slate-400 text-sm"><Wrench size={30} className="mx-auto mb-2 opacity-50" />No maintenance requests.</div>
          : (<table className="w-full text-left"><thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Date", "Facility", "Type", "Cost", "Requested by", "Status"].map((h) => (<th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">{rows.map((m) => (<tr key={m.id} className="hover:bg-slate-50/70">
              <td className="px-4 py-3 text-xs text-slate-400">{m.request_date ? formatDate(m.request_date) : "—"}</td>
              <td className="px-4 py-3 text-sm font-bold text-slate-900">{m.facility_name || "—"}{m.comment && <p className="text-xs font-normal text-slate-400 line-clamp-1">{m.comment}</p>}</td>
              <td className="px-4 py-3 text-sm text-slate-600">{m.maintenance_type || "—"}</td>
              <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{Number(m.total_cost).toLocaleString()}</td>
              <td className="px-4 py-3 text-xs text-slate-500">{m.requester_name || "—"}</td>
              <td className="px-4 py-3">{canWrite ? <select value={m.status} onChange={(e) => save.mutate({ id: m.id, data: { status: e.target.value } })} className={cn("text-xs font-semibold rounded-lg border px-2 py-1 capitalize", STATUS_STYLE[m.status])}>{STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select> : <span className={cn("badge capitalize", STATUS_STYLE[m.status])}>{m.status.replace("_", " ")}</span>}</td>
            </tr>))}</tbody></table>)}
      </div>
    </div>
  );
}
