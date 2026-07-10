"use client";

import { useState, useEffect } from "react";
import {
  useReportWorkflow, useCreateReportWorkflow, useUpdateReportWorkflow, useDeleteReportWorkflow,
} from "@/hooks/useAcademics";
import { useClassOptions } from "@/hooks/useEnrollment";
import { useCurrentSession } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { FolderOpen, Plus, X, Loader2, Trash2, AlertTriangle } from "lucide-react";
import { TERMS } from "@/lib/terms";

const STAGES = ["draft", "submitted", "reviewed", "approved", "published"];
const STAGE_STYLE: Record<string, string> = {
  draft: "bg-slate-50 text-slate-500 border-slate-200",
  submitted: "bg-blue-50 text-blue-700 border-blue-200",
  reviewed: "bg-indigo-50 text-indigo-700 border-indigo-200",
  approved: "bg-amber-50 text-amber-700 border-amber-200",
  published: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

export default function ReportWorkflowPage() {
  const canWrite = useHasPermission("school:reports:write");
  const [stageFilter, setStageFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ class_id: "", academic_year: "", term: "", notes: "" });

  const { data, isLoading, isError, refetch } = useReportWorkflow(stageFilter ? { stage: stageFilter } : undefined);
  const { data: classData } = useClassOptions();
  const classes = (classData?.items ?? []) as Array<{ id: string; name: string }>;
  const create = useCreateReportWorkflow();
  const update = useUpdateReportWorkflow();
  const remove = useDeleteReportWorkflow();

  const { data: cur } = useCurrentSession();
  useEffect(() => { if (cur?.term || cur?.name) setForm((f) => ({ ...f, term: f.term || cur?.term || "", academic_year: f.academic_year || cur?.name || "" })); }, [cur?.term, cur?.name]);

  const reset = () => { setForm({ class_id: "", academic_year: cur?.name || "", term: cur?.term || "", notes: "" }); setShowForm(false); };
  const submit = () => create.mutate(
    { class_id: form.class_id || null, academic_year: form.academic_year || null, term: form.term || null, notes: form.notes || null },
    { onSuccess: reset },
  );

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Academics</span><span>/</span><span className="text-brand-600 font-semibold">Report Workflow</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Report Workflow</h1>
          <p className="text-slate-500 text-sm mt-0.5">Move report cards through draft → submitted → reviewed → approved → published.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Workflow</button>}
      </div>

      <div className="mb-5">
        <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All stages</option>{STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">New Report Workflow</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Class</label>
              <select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} className="input">
                <option value="">Select class…</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div><label className="label">Academic Year</label><input value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} className="input" placeholder="2025/2026" /></div>
            <div><label className="label">Term</label><select value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="input"><option value="">— Term —</option>{TERMS.map((t) => (<option key={t} value={t}>{t}</option>))}</select></div>
            <div className="md:col-span-3"><label className="label">Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Class", "Year / Term", "Stage", "Updated", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 5 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={5} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load workflows.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{r.class_name || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{[r.academic_year, r.term].filter(Boolean).join(" · ") || "—"}</td>
                  <td className="px-5 py-4">
                    {canWrite ? (
                      <select value={r.stage} onChange={(e) => update.mutate({ id: r.id, data: { stage: e.target.value } })} className={cn("input py-1 text-xs capitalize w-36 border", STAGE_STYLE[r.stage] || "")}>
                        {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    ) : <span className={cn("badge capitalize", STAGE_STYLE[r.stage] || "")}>{r.stage}</span>}
                  </td>
                  <td className="px-5 py-4 text-xs text-slate-500">{formatDate(r.updated_at)}</td>
                  <td className="px-5 py-4">{canWrite && <button onClick={() => { if (confirm("Delete this workflow?")) remove.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={5} className="py-16 text-center text-slate-400"><FolderOpen size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No report workflows yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
