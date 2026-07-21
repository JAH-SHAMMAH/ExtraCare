"use client";

import { useState } from "react";
import { useEcPrograms, useCreateEcProgram, useUpdateEcProgram, useDeleteEcProgram, type EcProgram } from "@/hooks/useEclassroom";
import { useSessions, useSections } from "@/hooks/usePlatform";
import { cn } from "@/lib/utils";
import { BookOpen, Plus, Loader2, AlertTriangle, Pencil, Trash2, X } from "lucide-react";

const CBT_TYPES = ["student", "staff"];
const BLANK = { name: "", description: "", cbt_type: "student", section_id: "", session_id: "", is_active: true };

export default function EcProgramsPage() {
  const [filters, setFilters] = useState({ cbt_type: "", section_id: "", session_id: "" });
  const { data, isLoading, isError, refetch } = useEcPrograms({
    cbt_type: filters.cbt_type || undefined, section_id: filters.section_id || undefined, session_id: filters.session_id || undefined,
  });
  const { data: sessions } = useSessions();
  const { data: sections } = useSections();
  const create = useCreateEcProgram();
  const update = useUpdateEcProgram();
  const del = useDeleteEcProgram();
  const rows = data ?? [];
  const sessionList: any[] = (sessions as any[]) ?? [];
  const sectionList: any[] = (sections as any[]) ?? [];

  const [show, setShow] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [f, setF] = useState({ ...BLANK });
  const reset = () => { setF({ ...BLANK }); setEditing(null); setShow(false); };
  const startEdit = (p: EcProgram) => { setF({ name: p.name, description: p.description ?? "", cbt_type: p.cbt_type, section_id: p.section_id ?? "", session_id: p.session_id ?? "", is_active: p.is_active }); setEditing(p.id); setShow(true); };
  const submit = () => {
    const payload = { name: f.name.trim(), description: f.description || null, cbt_type: f.cbt_type, section_id: f.section_id || null, session_id: f.session_id || null, is_active: f.is_active };
    if (editing) update.mutate({ id: editing, data: payload }, { onSuccess: reset });
    else create.mutate(payload, { onSuccess: reset });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>eClassroom</span><span>/</span><span className="text-brand-600 font-semibold">Programs</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Program Manager</h1>
          <p className="text-slate-500 text-sm mt-0.5">CBT-linked learning programs, by school and session.</p>
        </div>
        <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Program</button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <select value={filters.cbt_type} onChange={(e) => setFilters({ ...filters, cbt_type: e.target.value })} className="input max-w-[150px] capitalize"><option value="">All CBT types</option>{CBT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select>
        <select value={filters.section_id} onChange={(e) => setFilters({ ...filters, section_id: e.target.value })} className="input max-w-[180px]"><option value="">All schools</option>{sectionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <select value={filters.session_id} onChange={(e) => setFilters({ ...filters, session_id: e.target.value })} className="input max-w-[180px]"><option value="">All sessions</option>{sessionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit program" : "New program"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2"><label className="label">Name *</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. JSS1 Maths CBT" /></div>
            <div><label className="label">CBT type</label><select value={f.cbt_type} onChange={(e) => setF({ ...f, cbt_type: e.target.value })} className="input capitalize">{CBT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
            <div><label className="label">School</label><select value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value })} className="input"><option value="">—</option>{sectionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <div><label className="label">Session</label><select value={f.session_id} onChange={(e) => setF({ ...f, session_id: e.target.value })} className="input"><option value="">—</option>{sessionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <div className="flex items-end gap-2 pb-1"><input type="checkbox" id="prog-active" checked={f.is_active} onChange={(e) => setF({ ...f, is_active: e.target.checked })} /><label htmlFor="prog-active" className="text-xs font-medium text-slate-700">Active</label></div>
            <div className="md:col-span-2"><label className="label">Description</label><textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input min-h-[60px]" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!f.name.trim() || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}Save</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load programs.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><BookOpen size={34} className="mb-3 opacity-40" /><p className="font-semibold">No programs yet</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((p) => (
            <div key={p.id} className={cn("flex items-center gap-3 px-5 py-3.5", !p.is_active && "opacity-60")}>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2"><p className="text-sm font-semibold text-slate-800 truncate">{p.name}</p><span className="badge bg-slate-100 text-slate-500 border-slate-200 capitalize">{p.cbt_type}</span></div>
                <p className="text-xs text-slate-400 truncate">{[p.section_name, p.session_name].filter(Boolean).join(" · ") || "—"}</p>
              </div>
              <button onClick={() => startEdit(p)} className="text-slate-400 hover:text-brand-600 p-1.5"><Pencil size={14} /></button>
              <button onClick={() => { if (confirm(`Remove “${p.name}”?`)) del.mutate(p.id); }} className="text-slate-400 hover:text-red-600 p-1.5"><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
