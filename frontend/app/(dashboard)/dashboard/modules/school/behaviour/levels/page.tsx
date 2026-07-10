"use client";

import { useState } from "react";
import Link from "next/link";
import { useBehaviourLevels, useSaveBehaviourLevel, useDeleteBehaviourLevel } from "@/hooks/useBehaviourConfig";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { ArrowLeft, Plus, Loader2, Edit2, Trash2, X, Gauge } from "lucide-react";
import type { BehaviourLevel } from "@/types";

const BLANK = { name: "", min_points: "", max_points: "", colour: "", description: "", is_active: true };

export default function BehaviourLevelsPage() {
  const canWrite = useHasPermission("school:behaviour:write");
  const { data, isLoading } = useBehaviourLevels();
  const save = useSaveBehaviourLevel();
  const remove = useDeleteBehaviourLevel();
  const levels: BehaviourLevel[] = data?.items || [];

  const [editing, setEditing] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState(BLANK);

  const reset = () => { setForm(BLANK); setEditing(null); setShow(false); };
  const startEdit = (l: BehaviourLevel) => {
    setForm({ name: l.name, min_points: String(l.min_points), max_points: l.max_points != null ? String(l.max_points) : "", colour: l.colour || "", description: l.description || "", is_active: l.is_active });
    setEditing(l.id); setShow(true);
  };
  const submit = () => {
    const payload = { name: form.name, min_points: Number(form.min_points), max_points: form.max_points === "" ? null : Number(form.max_points), colour: form.colour || null, description: form.description || null, is_active: form.is_active };
    save.mutate({ id: editing || undefined, data: payload }, { onSuccess: reset });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/behaviour" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Behaviour Tracker</Link>
      <div className="flex items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Behaviour Tracker</span><span>/</span><span className="text-brand-600 font-semibold">Levels</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Behaviour Levels</h1>
          <p className="text-slate-500 text-sm mt-0.5">Named conduct bands by point range. A student is classified by their cumulative points (leave the top blank for an open-ended band).</p>
        </div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> Add level</button>}
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit level" : "New level"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="label">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="e.g. Excellent" />
            </div>
            <div>
              <label className="label">Accent colour</label>
              <input value={form.colour} onChange={(e) => setForm({ ...form, colour: e.target.value })} className="input" placeholder="e.g. emerald (optional)" />
            </div>
            <div>
              <label className="label">Min points (inclusive)</label>
              <input type="number" value={form.min_points} onChange={(e) => setForm({ ...form, min_points: e.target.value })} className="input" placeholder="can be negative" />
            </div>
            <div>
              <label className="label">Max points (inclusive)</label>
              <input type="number" value={form.max_points} onChange={(e) => setForm({ ...form, max_points: e.target.value })} className="input" placeholder="blank = no upper cap" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={2} />
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="lvl-active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <label htmlFor="lvl-active" className="text-xs font-medium text-slate-700">Active (used for classification)</label>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.name || form.min_points === "" || save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : levels.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><Gauge size={30} className="mx-auto mb-2 opacity-50" />No levels defined yet.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Level", "Range", "Status", ""].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {levels.map((l) => (
                <tr key={l.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-3 text-sm font-bold text-slate-900">{l.name}{l.description && <p className="text-xs font-normal text-slate-400 mt-0.5">{l.description}</p>}</td>
                  <td className="px-5 py-3 text-sm text-slate-600 tabular-nums">{l.min_points} {l.max_points != null ? `to ${l.max_points}` : "and up"}</td>
                  <td className="px-5 py-3">{l.is_active ? <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">Active</span> : <span className="badge bg-slate-50 text-slate-400 border-slate-200">Inactive</span>}</td>
                  <td className="px-5 py-3">
                    {canWrite ? (
                      <div className="flex items-center gap-3">
                        <button onClick={() => startEdit(l)} className="text-xs text-brand-600 font-semibold hover:underline inline-flex items-center gap-1"><Edit2 size={13} />Edit</button>
                        <button onClick={() => { if (confirm(`Delete "${l.name}"?`)) remove.mutate(l.id); }} className="text-xs text-rose-600 font-semibold hover:underline inline-flex items-center gap-1"><Trash2 size={13} />Delete</button>
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
