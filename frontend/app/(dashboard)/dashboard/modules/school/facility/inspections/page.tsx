"use client";

import { useState } from "react";
import Link from "next/link";
import { cn, formatDate } from "@/lib/utils";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { useFacilityInspections, useSaveInspection, useDeleteInspection, useFacilities, useFacilityComplaints } from "@/hooks/useFacility";
import { ArrowLeft, Plus, X, Loader2, Trash2, ClipboardCheck } from "lucide-react";
import type { FacilityInspection } from "@/types";

export default function FacilityInspectionsPage() {
  const canWrite = useHasPermission("school_admin:facility:write");
  const [mine, setMine] = useState(true);
  const { data, isLoading } = useFacilityInspections(mine);
  const { data: facilities } = useFacilities();
  const { data: complaints } = useFacilityComplaints(false);
  const save = useSaveInspection();
  const del = useDeleteInspection();
  const rows: FacilityInspection[] = data || [];
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ facility_id: "", complaint_id: "", comment: "", outcome: "" });
  const reset = () => { setForm({ facility_id: "", complaint_id: "", comment: "", outcome: "" }); setShow(false); };
  const submit = () => save.mutate({ facility_id: form.facility_id || null, complaint_id: form.complaint_id || null, comment: form.comment || null, outcome: form.outcome || null }, { onSuccess: reset });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/facility" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Facility Management</Link>
      <div className="flex items-end justify-between mb-4 gap-4">
        <div><nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Facility Management</span><span>/</span><span className="text-brand-600 font-semibold">Inspections</span></nav><h1 className="text-2xl font-black text-slate-900 tracking-tight">Facility Inspections</h1></div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> New Inspection</button>}
      </div>
      <div className="flex bg-slate-100 rounded-lg p-0.5 w-fit mb-4"><button onClick={() => setMine(true)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", mine ? "bg-white shadow" : "text-slate-600")}>My Inspections</button><button onClick={() => setMine(false)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", !mine ? "bg-white shadow" : "text-slate-600")}>All Inspections</button></div>
      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New inspection</h2><button onClick={reset}><X size={18} className="text-slate-400" /></button></div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Facility</label><select value={form.facility_id} onChange={(e) => setForm({ ...form, facility_id: e.target.value })} className="input"><option value="">—</option>{(facilities || []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></div>
            <div><label className="label">Complaint (optional)</label><select value={form.complaint_id} onChange={(e) => setForm({ ...form, complaint_id: e.target.value })} className="input"><option value="">—</option>{(complaints || []).map((c) => <option key={c.id} value={c.id}>{c.reference} · {c.title}</option>)}</select></div>
            <div><label className="label">Outcome</label><select value={form.outcome} onChange={(e) => setForm({ ...form, outcome: e.target.value })} className="input"><option value="">—</option><option value="ok">OK</option><option value="needs_attention">Needs attention</option><option value="failed">Failed</option></select></div>
            <div className="md:col-span-2"><label className="label">Comment</label><textarea value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} className="input" rows={3} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Record</button></div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <div className="py-16 text-center text-slate-400 text-sm"><ClipboardCheck size={30} className="mx-auto mb-2 opacity-50" />No inspections.</div>
          : (<table className="w-full text-left"><thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Facility", "Inspector", "Comment", "Outcome", "Date", ""].map((h) => (<th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">{rows.map((r) => (<tr key={r.id} className="hover:bg-slate-50/70">
              <td className="px-4 py-3 text-sm font-bold text-slate-900">{r.facility_name || "—"}</td>
              <td className="px-4 py-3 text-xs text-slate-500">{r.inspector_name || "—"}</td>
              <td className="px-4 py-3 text-sm text-slate-600 max-w-xs line-clamp-2">{r.comment || "—"}</td>
              <td className="px-4 py-3 text-sm capitalize text-slate-600">{r.outcome?.replace("_", " ") || "—"}</td>
              <td className="px-4 py-3 text-xs text-slate-400">{r.inspection_date ? formatDate(r.inspection_date) : "—"}</td>
              <td className="px-4 py-3">{canWrite && <button onClick={() => { if (confirm("Delete inspection?")) del.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
            </tr>))}</tbody></table>)}
      </div>
    </div>
  );
}
