"use client";

import { useState } from "react";
import {
  useSubjectSelections, useCreateSelection, useUpdateSelection, useDeleteSelection, useSubjectOptions,
} from "@/hooks/useAcademics";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import { BookMarked, Plus, X, Loader2, Trash2, AlertTriangle } from "lucide-react";
import { TERMS } from "@/lib/terms";

const STATUSES = ["requested", "approved", "rejected"];
const STATUS_STYLE: Record<string, string> = {
  requested: "bg-amber-50 text-amber-700 border-amber-200",
  approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
};

const EMPTY = { student_id: "", subject_id: "", academic_year: "", term: "", status: "requested" };

export default function SubjectSelectionPage() {
  const canWrite = useHasPermission("school:subjects:write");
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...EMPTY });

  const { data, isLoading, isError, refetch } = useSubjectSelections(statusFilter ? { status: statusFilter } : undefined);
  const { data: subjData } = useSubjectOptions();
  const subjects = (subjData?.items ?? []) as Array<{ id: string; name: string }>;
  const create = useCreateSelection();
  const update = useUpdateSelection();
  const remove = useDeleteSelection();

  const reset = () => { setForm({ ...EMPTY }); setShowForm(false); };
  const submit = () => create.mutate(
    { student_id: form.student_id, subject_id: form.subject_id, academic_year: form.academic_year || null, term: form.term || null, status: form.status },
    { onSuccess: reset },
  );

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Academics</span><span>/</span><span className="text-brand-600 font-semibold">Subject Selection</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Subject Selection</h1>
          <p className="text-slate-500 text-sm mt-0.5">Assign and approve students’ elective subjects.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Selection</button>}
      </div>

      <div className="mb-5">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">New Subject Selection</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>
            <div><label className="label">Subject *</label>
              <select value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} className="input">
                <option value="">Select subject…</option>{subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div><label className="label">Academic Year</label><input value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} className="input" placeholder="2025/2026" /></div>
            <div><label className="label">Term</label><select value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="input"><option value="">— Term —</option>{TERMS.map((t) => (<option key={t} value={t}>{t}</option>))}</select></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.student_id || !form.subject_id || create.isPending} className="btn-primary gap-2">
              {create.isPending && <Loader2 size={15} className="animate-spin" />}Save
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Subject", "Year / Term", "Status", "Added", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load selections.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((s) => (
                <tr key={s.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{s.student_name || s.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{s.subject_name || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{[s.academic_year, s.term].filter(Boolean).join(" · ") || "—"}</td>
                  <td className="px-5 py-4">
                    {canWrite ? (
                      <select value={s.status} onChange={(e) => update.mutate({ id: s.id, data: { status: e.target.value } })} className={cn("input py-1 text-xs capitalize w-32 border", STATUS_STYLE[s.status] || "")}>
                        {STATUSES.map((x) => <option key={x} value={x}>{x}</option>)}
                      </select>
                    ) : <span className={cn("badge capitalize", STATUS_STYLE[s.status] || "")}>{s.status}</span>}
                  </td>
                  <td className="px-5 py-4 text-xs text-slate-500">{formatDate(s.created_at)}</td>
                  <td className="px-5 py-4">{canWrite && <button onClick={() => { if (confirm("Remove this selection?")) remove.mutate(s.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><BookMarked size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No selections yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
