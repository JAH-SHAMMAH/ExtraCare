"use client";

import { useState } from "react";
import Link from "next/link";
import { useBehaviourCategories, useSaveBehaviourCategory, useDeleteBehaviourCategory } from "@/hooks/useBehaviourConfig";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { ArrowLeft, Plus, Loader2, Edit2, Trash2, X, Tags } from "lucide-react";
import type { BehaviourCategory, BehaviourType } from "@/types";

const TYPE_STYLE: Record<BehaviourType, string> = {
  positive: "bg-emerald-50 text-emerald-700 border-emerald-200",
  negative: "bg-rose-50 text-rose-700 border-rose-200",
  neutral: "bg-slate-50 text-slate-600 border-slate-200",
};

const BLANK = { name: "", type: "positive" as BehaviourType, default_points: "", description: "", is_active: true };

export default function BehaviourCategoriesPage() {
  const canWrite = useHasPermission("school:behaviour:write");
  const { data, isLoading } = useBehaviourCategories();
  const save = useSaveBehaviourCategory();
  const remove = useDeleteBehaviourCategory();
  const cats: BehaviourCategory[] = data?.items || [];

  const [editing, setEditing] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState(BLANK);

  const reset = () => { setForm(BLANK); setEditing(null); setShow(false); };
  const startEdit = (c: BehaviourCategory) => {
    setForm({ name: c.name, type: c.type, default_points: c.default_points != null ? String(c.default_points) : "", description: c.description || "", is_active: c.is_active });
    setEditing(c.id); setShow(true);
  };
  const submit = () => {
    const payload = { name: form.name, type: form.type, default_points: form.default_points === "" ? null : Number(form.default_points), description: form.description || null, is_active: form.is_active };
    save.mutate({ id: editing || undefined, data: payload }, { onSuccess: reset });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/behaviour" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Behaviour Tracker</Link>
      <div className="flex items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Behaviour Tracker</span><span>/</span><span className="text-brand-600 font-semibold">Manage</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Behaviour Categories</h1>
          <p className="text-slate-500 text-sm mt-0.5">The top-level behaviours you track. Records file under these; sub-manage adds finer sub-categories.</p>
        </div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> Add category</button>}
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit category" : "New category"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="label">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="e.g. Punctuality" />
            </div>
            <div>
              <label className="label">Type</label>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as BehaviourType })} className="input">
                <option value="positive">Positive</option>
                <option value="negative">Negative</option>
                <option value="neutral">Neutral</option>
              </select>
            </div>
            <div>
              <label className="label">Default points</label>
              <input type="number" value={form.default_points} onChange={(e) => setForm({ ...form, default_points: e.target.value })} className="input" placeholder="optional (can be negative)" />
            </div>
            <div className="flex items-center gap-2 mt-6">
              <input type="checkbox" id="active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <label htmlFor="active" className="text-xs font-medium text-slate-700">Active</label>
            </div>
            <div className="md:col-span-2">
              <label className="label">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={2} />
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
        ) : cats.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><Tags size={30} className="mx-auto mb-2 opacity-50" />No categories yet.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Category", "Type", "Default pts", "Status", ""].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {cats.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-3 text-sm font-bold text-slate-900">{c.name}{c.description && <p className="text-xs font-normal text-slate-400 mt-0.5">{c.description}</p>}</td>
                  <td className="px-5 py-3"><span className={cn("badge capitalize", TYPE_STYLE[c.type])}>{c.type}</span></td>
                  <td className="px-5 py-3 text-sm text-slate-600 tabular-nums">{c.default_points ?? "—"}</td>
                  <td className="px-5 py-3">{c.is_active ? <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">Active</span> : <span className="badge bg-slate-50 text-slate-400 border-slate-200">Inactive</span>}</td>
                  <td className="px-5 py-3">
                    {canWrite ? (
                      <div className="flex items-center gap-3">
                        <button onClick={() => startEdit(c)} className="text-xs text-brand-600 font-semibold hover:underline inline-flex items-center gap-1"><Edit2 size={13} />Edit</button>
                        <button onClick={() => { if (confirm(`Delete "${c.name}"? Deactivate instead if it's in use.`)) remove.mutate(c.id); }} className="text-xs text-rose-600 font-semibold hover:underline inline-flex items-center gap-1"><Trash2 size={13} />Delete</button>
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
