"use client";

import { useState } from "react";
import Link from "next/link";
import { useAssessmentCriteria, useSaveAssessmentCriterion, useDeleteAssessmentCriterion } from "@/hooks/usePeople";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { ArrowLeft, Plus, Loader2, Edit2, Trash2, X, SlidersHorizontal } from "lucide-react";
import type { AssessmentCriterion } from "@/types";

const BLANK = { name: "", description: "", category: "", weight: "1", max_score: "5", is_active: true };

export default function AssessmentSetupPage() {
  const canWrite = useHasPermission("hr:write");
  const { data, isLoading } = useAssessmentCriteria();
  const save = useSaveAssessmentCriterion();
  const remove = useDeleteAssessmentCriterion();
  const criteria: AssessmentCriterion[] = data?.items || [];

  const [editing, setEditing] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState(BLANK);

  const reset = () => { setForm(BLANK); setEditing(null); setShow(false); };
  const startEdit = (c: AssessmentCriterion) => {
    setForm({ name: c.name, description: c.description || "", category: c.category || "", weight: String(c.weight), max_score: String(c.max_score), is_active: c.is_active });
    setEditing(c.id); setShow(true);
  };
  const submit = () => {
    const payload = {
      name: form.name, description: form.description || null, category: form.category || null,
      weight: Number(form.weight) || 1, max_score: Number(form.max_score) || 5, is_active: form.is_active,
    };
    save.mutate({ id: editing || undefined, data: payload }, { onSuccess: reset });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/staff-assessment" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Staff Assessment</Link>
      <div className="flex items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Staff Management</span><span>/</span><span className="text-brand-600 font-semibold">Setup</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Setup Staff Assessment</h1>
          <p className="text-slate-500 text-sm mt-0.5">Define the rubric criteria appraisals are scored against. Each criterion has a weight and a rating scale; the overall rating is their weighted average.</p>
        </div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> Add criterion</button>}
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit criterion" : "New criterion"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="label">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="e.g. Teaching Quality" />
            </div>
            <div>
              <label className="label">Category</label>
              <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="input" placeholder="optional, e.g. Instruction" />
            </div>
            <div>
              <label className="label">Weight</label>
              <input type="number" min="1" value={form.weight} onChange={(e) => setForm({ ...form, weight: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Rating scale (max)</label>
              <input type="number" min="1" max="100" value={form.max_score} onChange={(e) => setForm({ ...form, max_score: e.target.value })} className="input" placeholder="e.g. 5" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={2} />
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="crit-active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <label htmlFor="crit-active" className="text-xs font-medium text-slate-700">Active (shown on the assessment form)</label>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.name || save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : criteria.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><SlidersHorizontal size={30} className="mx-auto mb-2 opacity-50" />No criteria yet — assessments fall back to a manual overall rating.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Criterion", "Category", "Weight", "Scale", "Status", ""].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {criteria.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-3 text-sm font-bold text-slate-900">{c.name}{c.description && <p className="text-xs font-normal text-slate-400 mt-0.5">{c.description}</p>}</td>
                  <td className="px-5 py-3 text-sm text-slate-600">{c.category || "—"}</td>
                  <td className="px-5 py-3 text-sm text-slate-600 tabular-nums">×{c.weight}</td>
                  <td className="px-5 py-3 text-sm text-slate-600 tabular-nums">1–{c.max_score}</td>
                  <td className="px-5 py-3">{c.is_active ? <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">Active</span> : <span className="badge bg-slate-50 text-slate-400 border-slate-200">Inactive</span>}</td>
                  <td className="px-5 py-3">
                    {canWrite ? (
                      <div className="flex items-center gap-3">
                        <button onClick={() => startEdit(c)} className="text-xs text-brand-600 font-semibold hover:underline inline-flex items-center gap-1"><Edit2 size={13} />Edit</button>
                        <button onClick={() => { if (confirm(`Delete "${c.name}"? Deactivate instead if it's used by past assessments.`)) remove.mutate(c.id); }} className="text-xs text-rose-600 font-semibold hover:underline inline-flex items-center gap-1"><Trash2 size={13} />Delete</button>
                      </div>
                    ) : <span className="text-xs text-slate-300">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
