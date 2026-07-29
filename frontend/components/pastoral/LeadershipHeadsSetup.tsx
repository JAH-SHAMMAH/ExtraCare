"use client";

import { useState } from "react";
import {
  useLeadershipRoles, useCreateLeadershipRole, useUpdateLeadershipRole, useDeleteLeadershipRole,
  usePastoralHeads, useCreatePastoralHead, useUpdatePastoralHead, useDeletePastoralHead,
} from "@/hooks/usePastoral";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { Plus, Trash2, Loader2, Power } from "lucide-react";

function Row({ r, canWrite, onToggle, onDelete, label, sub }: {
  r: any; canWrite: boolean; onToggle: () => void; onDelete: () => void; label: React.ReactNode; sub?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-5 py-3 gap-3">
      <div className="min-w-0"><p className="text-sm font-semibold text-slate-800">{label}</p>{sub && <p className="text-xs text-slate-400 truncate">{sub}</p>}</div>
      <div className="flex items-center gap-2 shrink-0">
        <span className={cn("badge", r.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{r.is_active ? "Active" : "Inactive"}</span>
        {canWrite && <>
          <button onClick={onToggle} className="text-slate-400 hover:text-amber-600 p-1"><Power size={15} /></button>
          <button onClick={() => { if (confirm("Delete this?")) onDelete(); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
        </>}
      </div>
    </div>
  );
}

export function LeadershipRolesSetup({ canWrite }: { canWrite: boolean }) {
  const { data: rows = [], isLoading } = useLeadershipRoles();
  const create = useCreateLeadershipRole();
  const update = useUpdateLeadershipRole();
  const del = useDeleteLeadershipRole();
  const [f, setF] = useState({ name: "", sort_order: "", description: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Role name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Head Boy" /></div>
          <div><label className="label">Order</label><input type="number" value={f.sort_order} onChange={(e) => setF({ ...f, sort_order: e.target.value })} className="input w-20" /></div>
          <div className="flex-1 min-w-[160px]"><label className="label">Description</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input" /></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), sort_order: f.sort_order ? Number(f.sort_order) : 0, description: f.description || null }, { onSuccess: () => setF({ name: "", sort_order: "", description: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Role</button>
        </div>
      )}
      {isLoading ? (
        <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (rows as any[]).length === 0 ? (
        <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No leadership roles yet.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {(rows as any[]).map((r) => (
            <Row key={r.id} r={r} canWrite={canWrite} label={<>{r.name} <span className="text-xs font-normal text-slate-400">· #{r.sort_order}</span></>} sub={r.description}
              onToggle={() => update.mutate({ id: r.id, data: { is_active: !r.is_active } })} onDelete={() => del.mutate(r.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

export function PastoralHeadsSetup({ canWrite }: { canWrite: boolean }) {
  const { data: rows = [], isLoading } = usePastoralHeads();
  const create = useCreatePastoralHead();
  const update = useUpdatePastoralHead();
  const del = useDeletePastoralHead();
  const [f, setF] = useState<{ user_id: string | null; title: string; scope: string }>({ user_id: null, title: "", scope: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]"><label className="label">Staff member</label><EntityPicker type="staff" value={f.user_id} onChange={(id) => setF({ ...f, user_id: id })} /></div>
          <div className="flex-1 min-w-[160px]"><label className="label">Title</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder="e.g. Head of Boarding" /></div>
          <div><label className="label">Scope</label><input value={f.scope} onChange={(e) => setF({ ...f, scope: e.target.value })} className="input w-36" placeholder="opt." /></div>
          <button onClick={() => f.user_id && f.title.trim() && create.mutate({ user_id: f.user_id, title: f.title.trim(), scope: f.scope || null }, { onSuccess: () => setF({ user_id: null, title: "", scope: "" }) })} disabled={!f.user_id || !f.title.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Head</button>
        </div>
      )}
      {isLoading ? (
        <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (rows as any[]).length === 0 ? (
        <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No pastoral heads yet.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {(rows as any[]).map((r) => (
            <Row key={r.id} r={r} canWrite={canWrite} label={<>{r.user_name || r.user_id.slice(0, 8)} <span className="text-xs font-normal text-slate-400">· {r.title}</span></>} sub={r.scope}
              onToggle={() => update.mutate({ id: r.id, data: { is_active: !r.is_active } })} onDelete={() => del.mutate(r.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
