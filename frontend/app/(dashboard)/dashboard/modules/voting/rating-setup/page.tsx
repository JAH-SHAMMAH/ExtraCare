"use client";

import { useState } from "react";
import { usePeriods, useCreatePeriod, useExtendPeriod, useDeletePeriod, type VPeriod } from "@/hooks/useVoting";
import { useSections } from "@/hooks/usePlatform";
import { cn } from "@/lib/utils";
import { CalendarClock, Plus, Loader2, AlertTriangle, Trash2, X } from "lucide-react";

const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");

export default function RatingSetupPage() {
  const { data, isLoading, isError, refetch } = usePeriods();
  const { data: sections } = useSections();
  const create = useCreatePeriod();
  const del = useDeletePeriod();
  const rows = data ?? [];
  const sectionList: any[] = (sections as any[]) ?? [];

  const [show, setShow] = useState(false);
  const [f, setF] = useState({ name: "", starts_at: "", ends_at: "", section_id: "" });
  const reset = () => { setF({ name: "", starts_at: "", ends_at: "", section_id: "" }); setShow(false); };
  const submit = () => create.mutate(
    { name: f.name.trim(), starts_at: f.starts_at ? new Date(f.starts_at).toISOString() : null, ends_at: f.ends_at ? new Date(f.ends_at).toISOString() : null, section_id: f.section_id || null },
    { onSuccess: reset },
  );

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Voting System</span><span>/</span><span className="text-brand-600 font-semibold">Rating Setup</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Voting Periods</h1>
          <p className="text-slate-500 text-sm mt-0.5">The monthly windows during which voting is open.</p>
        </div>
        <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Month</button>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New voting period</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Month / name *</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. January" /></div>
            <div><label className="label">School</label><select value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value })} className="input"><option value="">—</option>{sectionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <div><label className="label">Starts at</label><input type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} className="input" /></div>
            <div><label className="label">Ends at</label><input type="datetime-local" value={f.ends_at} onChange={(e) => setF({ ...f, ends_at: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Save</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load periods.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><CalendarClock size={34} className="mb-3 opacity-40" /><p className="font-semibold">No voting periods yet</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Month", "Starts at", "Ends at", "Status", ""].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((p) => <Row key={p.id} p={p} onDelete={() => { if (confirm(`Delete “${p.name}”?`)) del.mutate(p.id); }} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Row({ p, onDelete }: { p: VPeriod; onDelete: () => void }) {
  const extend = useExtendPeriod();
  const [showExt, setShowExt] = useState(false);
  const [ends, setEnds] = useState(p.ends_at ? p.ends_at.slice(0, 16) : "");
  return (
    <tr className="hover:bg-slate-50/70">
      <td className="px-5 py-3 font-semibold text-slate-800">{p.name}</td>
      <td className="px-5 py-3 text-slate-600">{fmt(p.starts_at)}</td>
      <td className="px-5 py-3 text-slate-600">{fmt(p.ends_at)}</td>
      <td className="px-5 py-3"><span className={cn("badge capitalize", p.status === "active" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500 border-slate-200")}>{p.status}</span></td>
      <td className="px-5 py-3">
        <div className="flex items-center gap-2">
          {showExt ? (
            <div className="flex items-center gap-1">
              <input type="datetime-local" value={ends} onChange={(e) => setEnds(e.target.value)} className="input py-1 text-xs" />
              <button onClick={() => extend.mutate({ id: p.id, data: { ends_at: new Date(ends).toISOString() } }, { onSuccess: () => setShowExt(false) })} disabled={!ends || extend.isPending} className="btn-primary py-1 text-xs">Save</button>
            </div>
          ) : (
            <button onClick={() => setShowExt(true)} className="text-xs font-semibold text-brand-600 hover:underline">Extend</button>
          )}
          <button onClick={onDelete} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>
        </div>
      </td>
    </tr>
  );
}
