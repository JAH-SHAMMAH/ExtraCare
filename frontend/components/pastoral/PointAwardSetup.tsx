"use client";

import { useState } from "react";
import {
  usePointTypes, useCreatePointType, useUpdatePointType, useDeletePointType,
  useAwardTypes, useCreateAwardType, useUpdateAwardType, useDeleteAwardType,
} from "@/hooks/usePastoral";
import { cn } from "@/lib/utils";
import { Plus, Trash2, Loader2, Power } from "lucide-react";

export function PointSystemSetup({ canWrite }: { canWrite: boolean }) {
  const { data: types = [], isLoading } = usePointTypes();
  const create = useCreatePointType();
  const update = useUpdatePointType();
  const del = useDeletePointType();
  const [f, setF] = useState({ name: "", scope: "weekly", max_point: "", category: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Reading" /></div>
          <div><label className="label">Type</label><select value={f.scope} onChange={(e) => setF({ ...f, scope: e.target.value })} className="input"><option value="weekly">Weekly</option><option value="sessional">Sessional</option></select></div>
          <div><label className="label">Max point</label><input type="number" value={f.max_point} onChange={(e) => setF({ ...f, max_point: e.target.value })} className="input w-24" /></div>
          <div><label className="label">Category</label><input value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} className="input w-32" /></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), scope: f.scope, max_point: f.max_point ? Number(f.max_point) : null, category: f.category || null }, { onSuccess: () => setF({ name: "", scope: "weekly", max_point: "", category: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add New Type</button>
        </div>
      )}
      <ConfigTable
        loading={isLoading} rows={types} canWrite={canWrite}
        columns={["Name", "Type", "Max Point", "Category", "Status", ""]}
        render={(t: any) => [t.name, <span key="s" className="capitalize">{t.scope}</span>, t.max_point ?? "—", t.category || "—"]}
        onToggle={(t) => update.mutate({ id: t.id, data: { is_active: !t.is_active } })}
        onDelete={(t) => del.mutate(t.id)}
      />
    </div>
  );
}

export function AwardSystemSetup({ canWrite }: { canWrite: boolean }) {
  const { data: types = [], isLoading } = useAwardTypes();
  const create = useCreateAwardType();
  const update = useUpdateAwardType();
  const del = useDeleteAwardType();
  const [f, setF] = useState({ name: "", min_point: "", max_point: "", description: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Best in Neatness" /></div>
          <div><label className="label">Min point</label><input type="number" value={f.min_point} onChange={(e) => setF({ ...f, min_point: e.target.value })} className="input w-24" /></div>
          <div><label className="label">Max point</label><input type="number" value={f.max_point} onChange={(e) => setF({ ...f, max_point: e.target.value })} className="input w-24" /></div>
          <div className="flex-1 min-w-[140px]"><label className="label">Description</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input" /></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), min_point: f.min_point ? Number(f.min_point) : null, max_point: f.max_point ? Number(f.max_point) : null, description: f.description || null }, { onSuccess: () => setF({ name: "", min_point: "", max_point: "", description: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add New Type</button>
        </div>
      )}
      <ConfigTable
        loading={isLoading} rows={types} canWrite={canWrite}
        columns={["Name", "Min Point", "Max Point", "Description", "Status", ""]}
        render={(t: any) => [t.name, t.min_point ?? "—", t.max_point ?? "—", t.description || "—"]}
        onToggle={(t) => update.mutate({ id: t.id, data: { is_active: !t.is_active } })}
        onDelete={(t) => del.mutate(t.id)}
      />
    </div>
  );
}

function ConfigTable({ loading, rows, columns, render, onToggle, onDelete, canWrite }: {
  loading: boolean; rows: any[]; columns: string[]; render: (r: any) => React.ReactNode[];
  onToggle: (r: any) => void; onDelete: (r: any) => void; canWrite: boolean;
}) {
  if (loading) return <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>;
  if (rows.length === 0) return <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">Nothing configured yet.</p>;
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
      <table className="w-full text-left">
        <thead><tr className="bg-slate-50/80 border-b border-slate-100">{columns.map((c) => <th key={c} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{c}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-50">
          {rows.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50/70">
              {render(r).map((cell, i) => <td key={i} className="px-4 py-3 text-sm text-slate-700">{cell}</td>)}
              <td className="px-4 py-3"><span className={cn("badge", r.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{r.is_active ? "Active" : "Inactive"}</span></td>
              <td className="px-4 py-3">
                {canWrite && <div className="flex gap-1">
                  <button onClick={() => onToggle(r)} className="text-slate-400 hover:text-amber-600 p-1" title="Toggle status"><Power size={15} /></button>
                  <button onClick={() => { if (confirm(`Delete ${r.name}?`)) onDelete(r); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
                </div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
