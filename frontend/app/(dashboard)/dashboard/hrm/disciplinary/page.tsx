"use client";

import { useState } from "react";
import { useCases, useCreateCase, useUpdateCase, useDeleteCase } from "@/hooks/useHrExtended";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import { Gavel, Plus, X, Loader2, Trash2, AlertTriangle, Lock } from "lucide-react";

const SEVERITY_STYLE: Record<string, string> = {
  minor: "bg-amber-50 text-amber-700 border-amber-200",
  major: "bg-orange-50 text-orange-700 border-orange-200",
  gross: "bg-rose-50 text-rose-700 border-rose-200",
};
const STATUS_STYLE: Record<string, string> = {
  open: "bg-blue-50 text-blue-700 border-blue-200",
  under_review: "bg-violet-50 text-violet-700 border-violet-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  dismissed: "bg-slate-50 text-slate-500 border-slate-200",
};
const STATUSES = ["open", "under_review", "resolved", "dismissed"];

export default function DisciplinaryPage() {
  const canWrite = useHasPermission("hr:write");
  const [filter, setFilter] = useState("");
  const { data, isLoading, isError, refetch } = useCases(filter || undefined);
  const create = useCreateCase();
  const update = useUpdateCase();
  const del = useDeleteCase();
  const [show, setShow] = useState(false);
  const [f, setF] = useState({ staff_user_id: "", title: "", description: "", severity: "minor", incident_on: "" });
  const reset = () => { setF({ staff_user_id: "", title: "", description: "", severity: "minor", incident_on: "" }); setShow(false); };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">Disciplinary</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Disciplinary Cases</h1>
          <p className="text-slate-500 text-sm mt-0.5">Confidential staff conduct records. Every case + status change is audit-logged.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Case</button>}
      </div>

      <div className="mb-5"><select value={filter} onChange={(e) => setFilter(e.target.value)} className="input max-w-[200px] capitalize"><option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div><label className="label">Staff member *</label><EntityPicker type="staff" value={f.staff_user_id || null} onChange={(id) => setF({ ...f, staff_user_id: id || "" })} /></div>
            <div><label className="label">Title *</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder="Late arrival policy breach" /></div>
            <div><label className="label">Severity</label><select value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })} className="input capitalize">{["minor", "major", "gross"].map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
            <div><label className="label">Incident date</label><input type="date" value={f.incident_on} onChange={(e) => setF({ ...f, incident_on: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Description</label><textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input min-h-[80px]" /></div>
          </div>
          <div className="flex justify-end gap-3"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={() => create.mutate({ staff_user_id: f.staff_user_id, title: f.title.trim(), description: f.description || null, severity: f.severity, incident_on: f.incident_on || null }, { onSuccess: reset })} disabled={!f.staff_user_id || !f.title.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Open case</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load cases.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (data ?? []).length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Gavel size={36} className="mb-3 opacity-40" /><p className="font-semibold">No disciplinary cases</p></div>
      ) : (
        <div className="space-y-3">
          {data!.map((c) => (
            <div key={c.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-900">{c.title}</p>
                  <p className="text-xs text-slate-500">{c.staff_name || "—"}{c.incident_on ? ` · ${formatDate(c.incident_on)}` : ""}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={cn("badge capitalize", SEVERITY_STYLE[c.severity])}>{c.severity}</span>
                  {canWrite ? (
                    <select value={c.status} onChange={(e) => update.mutate({ id: c.id, data: { status: e.target.value, resolved_on: ["resolved", "dismissed"].includes(e.target.value) ? new Date().toISOString().slice(0, 10) : null } })} className={cn("text-xs font-semibold rounded-lg border px-2 py-1 capitalize", STATUS_STYLE[c.status])}>
                      {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                    </select>
                  ) : <span className={cn("badge capitalize", STATUS_STYLE[c.status])}>{c.status.replace("_", " ")}</span>}
                  {canWrite && <button onClick={() => { if (confirm("Delete this case?")) del.mutate(c.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
                </div>
              </div>
              {c.description && <p className="text-sm text-slate-600 mt-2">{c.description}</p>}
              {canWrite && (
                <input
                  defaultValue={c.action_taken || ""}
                  onBlur={(e) => { if (e.target.value !== (c.action_taken || "")) update.mutate({ id: c.id, data: { action_taken: e.target.value } }); }}
                  className="input mt-3 text-sm" placeholder="Action taken (saved on blur)…"
                />
              )}
            </div>
          ))}
        </div>
      )}
      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> Disciplinary records are HR-admin only (hr:write).</p>}
    </div>
  );
}
