"use client";

import { useState } from "react";
import { useActivities, useCreateActivity, useUpdateActivity, useDeleteActivity } from "@/hooks/useTimetableModule";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { Palette, Plus, X, Loader2, Trash2, Edit2, Lock } from "lucide-react";
import type { SchoolActivity } from "@/types";

export default function ManageActivitiesPage() {
  const canWrite = useHasPermission("school:timetable:write");
  const { data, isLoading } = useActivities();
  const create = useCreateActivity();
  const update = useUpdateActivity();
  const del = useDeleteActivity();

  const [editing, setEditing] = useState<SchoolActivity | null>(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: "", color: "#22c55e" });
  const activities: SchoolActivity[] = data?.items ?? [];

  const submit = () => {
    const payload = { name: form.name.trim(), color: form.color };
    if (editing) update.mutate({ id: editing.id, data: payload }, { onSuccess: () => setEditing(null) });
    else create.mutate(payload, { onSuccess: () => { setShow(false); setForm({ name: "", color: "#22c55e" }); } });
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>TimeTable</span><span>/</span><span className="text-brand-600 font-semibold">Manage Activities</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">School Activities</h1>
          <p className="text-slate-500 text-sm mt-0.5">Colour-coded non-lesson activities for the schedule grid.</p>
        </div>
        {canWrite && <button onClick={() => { setShow(true); setForm({ name: "", color: "#22c55e" }); }} className="btn-primary gap-2"><Plus size={15} /> Create Activity</button>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Activity Name", "Action"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={3} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
            : activities.length > 0 ? activities.map((a, i) => (
              <tr key={a.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
                <td className="px-5 py-3 text-sm font-semibold text-slate-800"><span className="inline-flex items-center gap-2">{a.name}<span className="inline-block w-3 h-4 rounded-sm" style={{ backgroundColor: a.color || "#cbd5e1" }} /></span></td>
                <td className="px-5 py-3">
                  {canWrite && <div className="flex items-center gap-1">
                    <button onClick={() => { setEditing(a); setForm({ name: a.name, color: a.color || "#22c55e" }); }} className="p-1.5 rounded text-amber-600 hover:bg-amber-50"><Edit2 size={15} /></button>
                    <button onClick={() => { if (confirm(`Delete ${a.name}?`)) del.mutate(a.id); }} className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={15} /></button>
                  </div>}
                </td>
              </tr>
            )) : <tr><td colSpan={3} className="py-16 text-center text-slate-400"><Palette size={32} className="mx-auto mb-2 opacity-40" /><p className="font-semibold">No activities yet</p></td></tr>}
          </tbody>
        </table>
      </div>
      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> Managing activities requires write access.</p>}

      {(show || editing) && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => { setShow(false); setEditing(null); }}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">{editing ? "Edit Activity" : "Add Activity"}</h3><button onClick={() => { setShow(false); setEditing(null); }} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 space-y-4">
              <div><label className="label">Activity Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
              <div><label className="label">Activity Color</label><div className="flex items-center gap-3"><input type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} className="h-10 w-16 rounded border border-slate-200 cursor-pointer" /><span className="text-sm text-slate-500">{form.color}</span></div></div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => { setShow(false); setEditing(null); }} className="btn-secondary">Close</button><button onClick={submit} disabled={!form.name.trim() || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}{editing ? "Save" : "Add"}</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
