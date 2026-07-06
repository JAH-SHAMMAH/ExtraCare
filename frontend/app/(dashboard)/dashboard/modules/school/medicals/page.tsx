"use client";

import { useState } from "react";
import {
  useMedicalRecords, useCreateMedicalRecord, useUpdateMedicalRecord, useDeleteMedicalRecord,
} from "@/hooks/usePastoral";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import { Loader2, Plus, X, Edit2, Trash2, AlertTriangle, Stethoscope, ShieldCheck } from "lucide-react";
import type { StudentMedicalRecord } from "@/types";

const TYPES = ["visit", "allergy", "medication", "immunization", "condition", "note"];
const SEVERITIES = ["low", "medium", "high"];
const SEV_STYLE: Record<string, string> = {
  low: "bg-slate-50 text-slate-500 border-slate-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  high: "bg-rose-50 text-rose-700 border-rose-200",
};

const EMPTY = { student_id: "", record_type: "visit", title: "", description: "", treatment: "", severity: "", recorded_on: "", follow_up_on: "" };

export default function MedicalsPage() {
  const canWrite = useHasPermission("medical:write");
  const [typeFilter, setTypeFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<StudentMedicalRecord | null>(null);
  const [form, setForm] = useState({ ...EMPTY });

  const { data, isLoading, isError, refetch } = useMedicalRecords(typeFilter ? { record_type: typeFilter } : undefined);
  const create = useCreateMedicalRecord();
  const update = useUpdateMedicalRecord();
  const remove = useDeleteMedicalRecord();

  const reset = () => { setForm({ ...EMPTY }); setEditing(null); setShowForm(false); };
  const openEdit = (r: StudentMedicalRecord) => {
    setForm({ student_id: r.student_id, record_type: r.record_type, title: r.title ?? "", description: r.description ?? "", treatment: r.treatment ?? "", severity: r.severity ?? "", recorded_on: r.recorded_on ?? "", follow_up_on: r.follow_up_on ?? "" });
    setEditing(r); setShowForm(true);
  };
  const submit = () => {
    const payload: Record<string, unknown> = {
      record_type: form.record_type, title: form.title || null, description: form.description || null,
      treatment: form.treatment || null, severity: form.severity || null,
      recorded_on: form.recorded_on || null, follow_up_on: form.follow_up_on || null,
    };
    if (editing) update.mutate({ id: editing.id, data: payload }, { onSuccess: reset });
    else { payload.student_id = form.student_id; create.mutate(payload, { onSuccess: reset }); }
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral &amp; Welfare</span><span>/</span><span className="text-brand-600 font-semibold">Medicals</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Medicals</h1>
          <p className="text-slate-500 text-sm mt-0.5">Confidential student health records.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Record</button>}
      </div>

      <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 mb-5">
        <ShieldCheck size={14} />
        Confidential — visible only to the school health officer and administrators. Every entry is audited.
      </div>

      <div className="mb-5">
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="input max-w-[200px] capitalize"><option value="">All record types</option>{TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select>
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Record" : "New Medical Record"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {!editing && <div><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>}
            <div><label className="label">Type</label><select value={form.record_type} onChange={(e) => setForm({ ...form, record_type: e.target.value })} className="input capitalize">{TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
            <div><label className="label">Title</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" /></div>
            <div><label className="label">Severity</label><select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} className="input capitalize"><option value="">—</option>{SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
            <div><label className="label">Recorded On</label><input type="date" value={form.recorded_on} onChange={(e) => setForm({ ...form, recorded_on: e.target.value })} className="input" /></div>
            <div><label className="label">Follow-up On</label><input type="date" value={form.follow_up_on} onChange={(e) => setForm({ ...form, follow_up_on: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Description</label><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={2} /></div>
            <div className="md:col-span-2"><label className="label">Treatment</label><textarea value={form.treatment} onChange={(e) => setForm({ ...form, treatment: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={(!editing && !form.student_id) || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}{editing ? "Update" : "Save"}</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Type", "Title", "Severity", "Recorded", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load records.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{r.student_name || r.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 capitalize">{r.record_type}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{r.title || "—"}</td>
                  <td className="px-5 py-4">{r.severity ? <span className={cn("badge capitalize", SEV_STYLE[r.severity] || "")}>{r.severity}</span> : <span className="text-slate-300">—</span>}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{r.recorded_on ? formatDate(r.recorded_on) : formatDate(r.created_at)}</td>
                  <td className="px-5 py-4">{canWrite && (
                    <div className="flex items-center gap-1">
                      <button onClick={() => openEdit(r)} className="text-slate-400 hover:text-brand-600 p-1"><Edit2 size={14} /></button>
                      <button onClick={() => { if (confirm("Remove this medical record?")) remove.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>
                    </div>
                  )}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><Stethoscope size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No medical records yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
