"use client";

import { useState } from "react";
import {
  useSessions, useCreateSession, useUpdateSession, useDeleteSession,
  useHouses, useCreateHouse, useDeleteHouse,
  useBands, useCreateBand, useDeleteBand,
} from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Settings, Loader2, Trash2, Plus, Pencil } from "lucide-react";
import { TERMS } from "@/lib/terms";
import type { AcademicSession } from "@/types";

type Tab = "sessions" | "houses" | "bands";

export default function SchoolSetupPage() {
  const canWrite = useHasPermission("settings:write");
  const [tab, setTab] = useState<Tab>("sessions");
  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-5">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Administration</span><span>/</span><span className="text-brand-600 font-semibold">School Setup</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">School Setup</h1>
        <p className="text-slate-500 text-sm mt-0.5">Academic sessions, houses and grading bands.</p>
      </div>
      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {([["sessions", "Sessions / Terms"], ["houses", "Houses"], ["bands", "Grading Bands"]] as [Tab, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>
      {tab === "sessions" ? <Sessions canWrite={canWrite} /> : tab === "houses" ? <Houses canWrite={canWrite} /> : <Bands canWrite={canWrite} />}
    </div>
  );
}

const BLANK_SESSION = { name: "", term: "", start_date: "", end_date: "", is_current: false };

function Sessions({ canWrite }: { canWrite: boolean }) {
  const { data } = useSessions();
  const create = useCreateSession();
  const update = useUpdateSession();
  const del = useDeleteSession();
  const [f, setF] = useState(BLANK_SESSION);
  const [editingId, setEditingId] = useState<string | null>(null);

  const reset = () => { setF(BLANK_SESSION); setEditingId(null); };
  const submit = () => {
    const payload = { name: f.name.trim(), term: f.term || null, start_date: f.start_date || null, end_date: f.end_date || null, is_current: f.is_current };
    if (editingId) update.mutate({ id: editingId, data: payload }, { onSuccess: reset });
    else create.mutate(payload, { onSuccess: reset });
  };
  const startEdit = (s: AcademicSession) => {
    setEditingId(s.id);
    setF({ name: s.name, term: s.term || "", start_date: s.start_date || "", end_date: s.end_date || "", is_current: s.is_current });
  };
  const busy = create.isPending || update.isPending;

  return (
    <>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <div><label className="label">Session *</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="2025/2026" /></div>
          <div><label className="label">Term</label><select value={f.term} onChange={(e) => setF({ ...f, term: e.target.value })} className="input"><option value="">— Term —</option>{TERMS.map((t) => (<option key={t} value={t}>{t}</option>))}</select></div>
          <div><label className="label">Start</label><input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} className="input" /></div>
          <div><label className="label">End</label><input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} className="input" /></div>
          <button onClick={submit} disabled={!f.name.trim() || busy} className="btn-primary justify-center">{busy ? <Loader2 size={14} className="animate-spin" /> : editingId ? "Update" : "Add"}</button>
          <div className="md:col-span-5 flex items-center justify-between">
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={f.is_current} onChange={(e) => setF({ ...f, is_current: e.target.checked })} /> Set as current session</label>
            {editingId && <button onClick={reset} className="text-xs text-slate-500 hover:underline">Cancel edit</button>}
          </div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {(data ?? []).length === 0 ? <p className="px-5 py-10 text-center text-slate-400 text-sm">No sessions yet.</p> : data!.map((s) => (
          <div key={s.id} className="flex items-center gap-3 px-5 py-3">
            <span className="text-sm font-semibold text-slate-800">{s.name}{s.term ? ` · ${s.term}` : ""}</span>
            {s.is_current && <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">current</span>}
            <span className="text-xs text-slate-400 ml-auto">{[s.start_date, s.end_date].filter(Boolean).join(" → ")}</span>
            {canWrite && !s.is_current && <button onClick={() => update.mutate({ id: s.id, data: { is_current: true } })} disabled={update.isPending} className="text-xs text-brand-600 font-semibold hover:underline">Make current</button>}
            {canWrite && <button onClick={() => startEdit(s)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Pencil size={13} /></button>}
            {canWrite && <button onClick={() => del.mutate(s.id)} className="text-slate-400 hover:text-red-600 p-1" title="Delete"><Trash2 size={14} /></button>}
          </div>
        ))}
      </div>
    </>
  );
}

function Houses({ canWrite }: { canWrite: boolean }) {
  const { data } = useHouses();
  const create = useCreateHouse();
  const del = useDeleteHouse();
  const [f, setF] = useState({ name: "", color: "", motto: "" });
  return (
    <>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div><label className="label">Name *</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" /></div>
          <div><label className="label">Color</label><input value={f.color} onChange={(e) => setF({ ...f, color: e.target.value })} className="input" placeholder="red" /></div>
          <div><label className="label">Motto</label><input value={f.motto} onChange={(e) => setF({ ...f, motto: e.target.value })} className="input" /></div>
          <button onClick={() => create.mutate({ name: f.name.trim(), color: f.color || null, motto: f.motto || null }, { onSuccess: () => setF({ name: "", color: "", motto: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary justify-center"><Plus size={14} /></button>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {(data ?? []).length === 0 ? <p className="col-span-full text-center text-slate-400 text-sm py-10">No houses yet.</p> : data!.map((h) => (
          <div key={h.id} className="bg-white rounded-xl border border-slate-200 p-4 flex items-start justify-between">
            <div><p className="text-sm font-bold text-slate-800">{h.name}</p><p className="text-xs text-slate-500">{h.color || ""}{h.motto ? ` · ${h.motto}` : ""}</p></div>
            {canWrite && <button onClick={() => del.mutate(h.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
          </div>
        ))}
      </div>
    </>
  );
}

function Bands({ canWrite }: { canWrite: boolean }) {
  const { data } = useBands();
  const create = useCreateBand();
  const del = useDeleteBand();
  const [f, setF] = useState({ grade: "", min_score: "", max_score: "", remark: "" });
  return (
    <>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <div><label className="label">Grade *</label><input value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value })} className="input" placeholder="A" /></div>
          <div><label className="label">Min *</label><input type="number" value={f.min_score} onChange={(e) => setF({ ...f, min_score: e.target.value })} className="input" /></div>
          <div><label className="label">Max *</label><input type="number" value={f.max_score} onChange={(e) => setF({ ...f, max_score: e.target.value })} className="input" /></div>
          <div><label className="label">Remark</label><input value={f.remark} onChange={(e) => setF({ ...f, remark: e.target.value })} className="input" placeholder="Excellent" /></div>
          <button onClick={() => create.mutate({ grade: f.grade.trim(), min_score: Number(f.min_score), max_score: Number(f.max_score), remark: f.remark || null }, { onSuccess: () => setF({ grade: "", min_score: "", max_score: "", remark: "" }) })} disabled={!f.grade.trim() || !f.min_score || !f.max_score || create.isPending} className="btn-primary justify-center"><Plus size={14} /></button>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {(data ?? []).length === 0 ? <p className="px-5 py-10 text-center text-slate-400 text-sm">No grading bands yet.</p> : data!.map((b) => (
          <div key={b.id} className="flex items-center gap-3 px-5 py-3">
            <span className="text-sm font-black text-slate-800 w-8">{b.grade}</span>
            <span className="text-sm text-slate-600">{b.min_score} – {b.max_score}</span>
            <span className="text-xs text-slate-400 ml-2">{b.remark || ""}</span>
            {canWrite && <button onClick={() => del.mutate(b.id)} className="text-slate-400 hover:text-red-600 p-1 ml-auto"><Trash2 size={14} /></button>}
          </div>
        ))}
      </div>
    </>
  );
}
