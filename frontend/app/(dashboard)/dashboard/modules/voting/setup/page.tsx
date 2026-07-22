"use client";

import { useState } from "react";
import { useVCategories, useCreateVCategory, useUpdateVCategory, useDeleteVCategory, type VCategory } from "@/hooks/useVoting";
import { useSections } from "@/hooks/usePlatform";
import { cn } from "@/lib/utils";
import { Trophy, Plus, Loader2, AlertTriangle, Pencil, Trash2, X, Check } from "lucide-react";

export default function VotingSetupPage() {
  const { data, isLoading, isError, refetch } = useVCategories();
  const { data: sections } = useSections();
  const create = useCreateVCategory();
  const rows = data ?? [];
  const sectionList: any[] = (sections as any[]) ?? [];

  const [show, setShow] = useState(false);
  const [f, setF] = useState({ description: "", section_id: "" });
  const reset = () => { setF({ description: "", section_id: "" }); setShow(false); };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Voting System</span><span>/</span><span className="text-brand-600 font-semibold">Voting Setup</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Categories</h1>
          <p className="text-slate-500 text-sm mt-0.5">Award categories votes are cast in.</p>
        </div>
        <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Add Category</button>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[220px]"><label className="label">Description *</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input" placeholder="e.g. Best Staff Award — Diction and Communication" /></div>
          <div className="min-w-[160px]"><label className="label">School</label><select value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value })} className="input"><option value="">—</option>{sectionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
          <button onClick={() => create.mutate({ description: f.description.trim(), section_id: f.section_id || null }, { onSuccess: reset })} disabled={!f.description.trim() || create.isPending} className="btn-primary gap-1.5">{create.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Add</button>
          <button onClick={reset} className="btn-secondary">Cancel</button>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load categories.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Trophy size={34} className="mb-3 opacity-40" /><p className="font-semibold">No categories yet</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((c) => <Row key={c.id} c={c} />)}
        </div>
      )}
    </div>
  );
}

function Row({ c }: { c: VCategory }) {
  const update = useUpdateVCategory();
  const del = useDeleteVCategory();
  const [editing, setEditing] = useState(false);
  const [desc, setDesc] = useState(c.description);
  return (
    <div className={cn("flex items-center gap-3 px-5 py-3.5", !c.is_active && "opacity-60")}>
      {editing ? (
        <>
          <input value={desc} onChange={(e) => setDesc(e.target.value)} className="input flex-1 py-1.5 text-sm" />
          <button onClick={() => update.mutate({ id: c.id, data: { description: desc.trim() } }, { onSuccess: () => setEditing(false) })} disabled={!desc.trim() || update.isPending} className="btn-primary gap-1 py-1.5 text-sm"><Check size={13} /> Save</button>
          <button onClick={() => { setEditing(false); setDesc(c.description); }} className="btn-secondary py-1.5 text-sm">Cancel</button>
        </>
      ) : (
        <>
          <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-800">{c.description}</p>{c.section_name && <p className="text-xs text-slate-400">{c.section_name}</p>}</div>
          <button onClick={() => update.mutate({ id: c.id, data: { is_active: !c.is_active } })} className={cn("text-[11px] font-bold uppercase px-2 py-1 rounded-full border", c.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-400 border-slate-200")}>{c.is_active ? "Active" : "Off"}</button>
          <button onClick={() => setEditing(true)} className="text-slate-400 hover:text-brand-600 p-1.5"><Pencil size={14} /></button>
          <button onClick={() => { if (confirm("Remove this category?")) del.mutate(c.id); }} className="text-slate-400 hover:text-red-600 p-1.5"><Trash2 size={14} /></button>
        </>
      )}
    </div>
  );
}
