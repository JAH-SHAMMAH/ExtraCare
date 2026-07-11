"use client";

import { useState } from "react";
import Link from "next/link";
import { cn, formatDate } from "@/lib/utils";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { useFacilityComplaints, useSaveComplaint, useDeleteComplaint, useFacilities } from "@/hooks/useFacility";
import { ArrowLeft, Plus, X, Loader2, Trash2, MessageSquareWarning } from "lucide-react";
import type { FacilityComplaint } from "@/types";

const STATUSES = ["open", "in_progress", "resolved", "closed"];
const STATUS_STYLE: Record<string, string> = { open: "bg-amber-50 text-amber-700 border-amber-200", in_progress: "bg-blue-50 text-blue-700 border-blue-200", resolved: "bg-emerald-50 text-emerald-700 border-emerald-200", closed: "bg-slate-50 text-slate-500 border-slate-200" };

export default function FacilityComplaintsPage() {
  const canWrite = useHasPermission("school_admin:facility:write");
  const [mine, setMine] = useState(true);
  const { data, isLoading } = useFacilityComplaints(mine);
  const { data: facilities } = useFacilities();
  const save = useSaveComplaint();
  const del = useDeleteComplaint();
  const rows: FacilityComplaint[] = data || [];
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", facility_id: "" });
  const reset = () => { setForm({ title: "", description: "", facility_id: "" }); setShow(false); };
  const submit = () => save.mutate({ data: { title: form.title, description: form.description || null, facility_id: form.facility_id || null } }, { onSuccess: reset });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/facility" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Facility Management</Link>
      <div className="flex items-end justify-between mb-4 gap-4">
        <div><nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Facility Management</span><span>/</span><span className="text-brand-600 font-semibold">Complaints</span></nav><h1 className="text-2xl font-black text-slate-900 tracking-tight">Facility Complaints</h1></div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> New Complaint</button>}
      </div>
      <div className="flex bg-slate-100 rounded-lg p-0.5 w-fit mb-4"><button onClick={() => setMine(true)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", mine ? "bg-white shadow" : "text-slate-600")}>My Complaints</button><button onClick={() => setMine(false)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", !mine ? "bg-white shadow" : "text-slate-600")}>All Complaints</button></div>
      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New complaint</h2><button onClick={reset}><X size={18} className="text-slate-400" /></button></div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Title</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" /></div>
            <div><label className="label">Facility</label><select value={form.facility_id} onChange={(e) => setForm({ ...form, facility_id: e.target.value })} className="input"><option value="">—</option>{(facilities || []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></div>
            <div className="md:col-span-2"><label className="label">Description</label><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={3} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.title || save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Lodge</button></div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <div className="py-16 text-center text-slate-400 text-sm"><MessageSquareWarning size={30} className="mx-auto mb-2 opacity-50" />No complaints.</div>
          : (
            <table className="w-full text-left"><thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Ref", "Title", "Facility", "Status", "Inspections", "Lodged", ""].map((h) => (<th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
              <tbody className="divide-y divide-slate-50">{rows.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3 text-xs font-mono text-slate-500">{c.reference}</td>
                  <td className="px-4 py-3 text-sm font-bold text-slate-900">{c.title}{c.description && <p className="text-xs font-normal text-slate-400 line-clamp-1">{c.description}</p>}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{c.facility_name || "—"}</td>
                  <td className="px-4 py-3">{canWrite ? <select value={c.status} onChange={(e) => save.mutate({ id: c.id, data: { status: e.target.value } })} className={cn("text-xs font-semibold rounded-lg border px-2 py-1 capitalize", STATUS_STYLE[c.status])}>{STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select> : <span className={cn("badge capitalize", STATUS_STYLE[c.status])}>{c.status.replace("_", " ")}</span>}</td>
                  <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{c.inspection_count}</td>
                  <td className="px-4 py-3 text-xs text-slate-400">{c.date_lodged ? formatDate(c.date_lodged) : "—"}<p>{c.lodger_name}</p></td>
                  <td className="px-4 py-3">{canWrite && <button onClick={() => { if (confirm("Delete complaint?")) del.mutate(c.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
                </tr>))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  );
}
