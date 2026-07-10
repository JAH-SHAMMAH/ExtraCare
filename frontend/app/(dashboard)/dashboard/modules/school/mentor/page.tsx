"use client";

import { useState, useEffect } from "react";
import {
  useMentorReports, useCreateMentorReport, useUpdateMentorReport, useDeleteMentorReport,
} from "@/hooks/usePastoral";
import { useCurrentTerm } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { formatDate } from "@/lib/utils";
import { Loader2, Plus, X, Edit2, Trash2, AlertTriangle, UserCheck } from "lucide-react";
import { TERMS } from "@/lib/terms";
import type { MentorReport } from "@/types";

const EMPTY = { student_id: "", term: "", period: "", summary: "", strengths: "", concerns: "", recommendations: "" };

export default function MentorPage() {
  const canWrite = useHasPermission("school:behaviour:write");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<MentorReport | null>(null);
  const [form, setForm] = useState({ ...EMPTY });
  const currentTerm = useCurrentTerm();
  useEffect(() => { if (currentTerm) setForm((f) => (f.term ? f : { ...f, term: currentTerm })); }, [currentTerm]);

  const { data, isLoading, isError, refetch } = useMentorReports();
  const create = useCreateMentorReport();
  const update = useUpdateMentorReport();
  const remove = useDeleteMentorReport();

  const reset = () => { setForm({ ...EMPTY, term: currentTerm }); setEditing(null); setShowForm(false); };
  const openEdit = (m: MentorReport) => {
    setForm({ student_id: m.student_id, term: m.term ?? "", period: m.period ?? "", summary: m.summary ?? "", strengths: m.strengths ?? "", concerns: m.concerns ?? "", recommendations: m.recommendations ?? "" });
    setEditing(m); setShowForm(true);
  };
  const submit = () => {
    const payload = { student_id: form.student_id, term: form.term || null, period: form.period || null, summary: form.summary || null, strengths: form.strengths || null, concerns: form.concerns || null, recommendations: form.recommendations || null };
    if (editing) update.mutate({ id: editing.id, data: payload }, { onSuccess: reset });
    else create.mutate(payload, { onSuccess: reset });
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral &amp; Welfare</span><span>/</span><span className="text-brand-600 font-semibold">Mentor Reports</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Mentor Reports</h1>
          <p className="text-slate-500 text-sm mt-0.5">Pastoral mentor reports on mentees.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Report</button>}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Report" : "New Report"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {!editing && <div><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>}
            <div><label className="label">Term</label><select value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="input"><option value="">— Term —</option>{TERMS.map((t) => (<option key={t} value={t}>{t}</option>))}</select></div>
            <div><label className="label">Period</label><input value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} className="input" placeholder="e.g. Week 1–6" /></div>
            <div className="md:col-span-3"><label className="label">Summary</label><textarea value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} className="input" rows={2} /></div>
            <div className="md:col-span-3"><label className="label">Strengths</label><textarea value={form.strengths} onChange={(e) => setForm({ ...form, strengths: e.target.value })} className="input" rows={2} /></div>
            <div className="md:col-span-3"><label className="label">Concerns</label><textarea value={form.concerns} onChange={(e) => setForm({ ...form, concerns: e.target.value })} className="input" rows={2} /></div>
            <div className="md:col-span-3"><label className="label">Recommendations</label><textarea value={form.recommendations} onChange={(e) => setForm({ ...form, recommendations: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={(!editing && !form.student_id) || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}{editing ? "Update" : "Create"}</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Mentor", "Term", "Summary", "Date", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load reports.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((m) => (
                <tr key={m.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{m.student_name || m.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{m.mentor_name || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{m.term || "—"}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 max-w-xs truncate">{m.summary || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{formatDate(m.created_at)}</td>
                  <td className="px-5 py-4">{canWrite && (
                    <div className="flex items-center gap-1">
                      <button onClick={() => openEdit(m)} className="text-slate-400 hover:text-brand-600 p-1"><Edit2 size={14} /></button>
                      <button onClick={() => { if (confirm("Delete this report?")) remove.mutate(m.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>
                    </div>
                  )}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><UserCheck size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No mentor reports yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
