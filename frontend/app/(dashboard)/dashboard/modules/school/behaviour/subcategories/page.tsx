"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useBehaviourCategories, useBehaviourSubcategories, useSaveBehaviourSubcategory, useDeleteBehaviourSubcategory } from "@/hooks/useBehaviourConfig";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { ArrowLeft, Plus, Loader2, Edit2, Trash2, X, ListTree } from "lucide-react";
import type { BehaviourCategory, BehaviourSubCategory } from "@/types";

const BLANK = { name: "", default_points: "", is_active: true };

export default function BehaviourSubcategoriesPage() {
  const canWrite = useHasPermission("school:behaviour:write");
  const { data: catData } = useBehaviourCategories();
  const cats: BehaviourCategory[] = catData?.items || [];
  const [categoryId, setCategoryId] = useState("");
  useEffect(() => { if (!categoryId && cats.length) setCategoryId(cats[0].id); }, [cats, categoryId]);

  const { data, isLoading } = useBehaviourSubcategories(categoryId || undefined);
  const save = useSaveBehaviourSubcategory();
  const remove = useDeleteBehaviourSubcategory();
  const subs: BehaviourSubCategory[] = data?.items || [];

  const [editing, setEditing] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState(BLANK);

  const reset = () => { setForm(BLANK); setEditing(null); setShow(false); };
  const startEdit = (s: BehaviourSubCategory) => {
    setForm({ name: s.name, default_points: s.default_points != null ? String(s.default_points) : "", is_active: s.is_active });
    setEditing(s.id); setShow(true);
  };
  const submit = () => {
    const payload = { category_id: categoryId, name: form.name, default_points: form.default_points === "" ? null : Number(form.default_points), is_active: form.is_active };
    save.mutate({ id: editing || undefined, data: payload }, { onSuccess: reset });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/behaviour" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Behaviour Tracker</Link>
      <div className="flex items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Behaviour Tracker</span><span>/</span><span className="text-brand-600 font-semibold">Sub-manage</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Behaviour Sub-categories</h1>
          <p className="text-slate-500 text-sm mt-0.5">Finer sub-items under a category — e.g. “Late to class” under “Punctuality”.</p>
        </div>
        {canWrite && !show && categoryId && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> Add sub-category</button>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
        <label className="label">Category</label>
        <select value={categoryId} onChange={(e) => { setCategoryId(e.target.value); reset(); }} className="input">
          <option value="">— Select a category —</option>
          {cats.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
        </select>
        {cats.length === 0 && <p className="text-xs text-amber-600 mt-2">No categories yet — create one under <Link href="/dashboard/modules/school/behaviour/categories" className="font-semibold hover:underline">Manage</Link> first.</p>}
      </div>

      {show && categoryId && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit sub-category" : "New sub-category"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="label">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="e.g. Late to class" />
            </div>
            <div>
              <label className="label">Default points</label>
              <input type="number" value={form.default_points} onChange={(e) => setForm({ ...form, default_points: e.target.value })} className="input" placeholder="optional; overrides category" />
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="sub-active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <label htmlFor="sub-active" className="text-xs font-medium text-slate-700">Active</label>
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
        ) : !categoryId ? (
          <div className="py-16 text-center text-slate-400 text-sm">Select a category to manage its sub-categories.</div>
        ) : subs.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><ListTree size={30} className="mx-auto mb-2 opacity-50" />No sub-categories under this category yet.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Sub-category", "Default pts", "Status", ""].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {subs.map((s) => (
                <tr key={s.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-3 text-sm font-bold text-slate-900">{s.name}</td>
                  <td className="px-5 py-3 text-sm text-slate-600 tabular-nums">{s.default_points ?? "—"}</td>
                  <td className="px-5 py-3">{s.is_active ? <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">Active</span> : <span className="badge bg-slate-50 text-slate-400 border-slate-200">Inactive</span>}</td>
                  <td className="px-5 py-3">
                    {canWrite ? (
                      <div className="flex items-center gap-3">
                        <button onClick={() => startEdit(s)} className="text-xs text-brand-600 font-semibold hover:underline inline-flex items-center gap-1"><Edit2 size={13} />Edit</button>
                        <button onClick={() => { if (confirm(`Delete "${s.name}"?`)) remove.mutate(s.id); }} className="text-xs text-rose-600 font-semibold hover:underline inline-flex items-center gap-1"><Trash2 size={13} />Delete</button>
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
