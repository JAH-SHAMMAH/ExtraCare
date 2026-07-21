"use client";

import { useState } from "react";
import { useConfirmations, useStartConfirmation, useDecideConfirmation, useCancelConfirmation, type Confirmation } from "@/hooks/useHrConfirmation";
import { useStaff } from "@/hooks/useUsers";
import { cn } from "@/lib/utils";
import { UserCheck, Plus, Loader2, AlertTriangle, Check, X, Trash2 } from "lucide-react";

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  confirmed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  declined: "bg-rose-50 text-rose-700 border-rose-200",
};
const FILTERS = ["all", "pending", "confirmed", "declined"];
const fmt = (d?: string | null) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : null);

export default function ConfirmationsPage() {
  const [status, setStatus] = useState("all");
  const { data, isLoading, isError, refetch } = useConfirmations(status === "all" ? undefined : status);
  const { data: staff } = useStaff();
  const start = useStartConfirmation();
  const staffList: any[] = (staff as any[]) ?? [];
  const rows = data ?? [];

  const [show, setShow] = useState(false);
  const [f, setF] = useState({ staff_user_id: "", probation_start: "", due_date: "", recommendation: "" });
  const reset = () => { setF({ staff_user_id: "", probation_start: "", due_date: "", recommendation: "" }); setShow(false); };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">Staff Confirmation</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Staff Confirmation</h1>
          <p className="text-slate-500 text-sm mt-0.5">Confirm staff at the end of probation — confirming updates their employment status.</p>
        </div>
        <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Start Confirmation</button>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="md:col-span-2"><label className="label">Staff *</label>
              <select value={f.staff_user_id} onChange={(e) => setF({ ...f, staff_user_id: e.target.value })} className="input">
                <option value="">Select a staff member…</option>
                {staffList.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.email}</option>)}
              </select>
            </div>
            <div><label className="label">Probation start</label><input type="date" value={f.probation_start} onChange={(e) => setF({ ...f, probation_start: e.target.value })} className="input" /></div>
            <div><label className="label">Confirmation due</label><input type="date" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Recommendation</label><input value={f.recommendation} onChange={(e) => setF({ ...f, recommendation: e.target.value })} className="input" placeholder="Optional" /></div>
          </div>
          <div className="flex justify-end gap-3">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={() => start.mutate({ staff_user_id: f.staff_user_id, probation_start: f.probation_start || null, due_date: f.due_date || null, recommendation: f.recommendation || null }, { onSuccess: reset })} disabled={!f.staff_user_id || start.isPending} className="btn-primary gap-2">{start.isPending && <Loader2 size={15} className="animate-spin" />}Start</button>
          </div>
        </div>
      )}

      <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit mb-5">
        {FILTERS.map((s) => <button key={s} onClick={() => setStatus(s)} className={cn("px-3 py-1.5 text-xs font-semibold rounded-md capitalize transition", status === s ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700")}>{s}</button>)}
      </div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load confirmations.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><UserCheck size={34} className="mb-3 opacity-40" /><p className="font-semibold">No confirmations{status !== "all" ? ` (${status})` : ""}</p></div>
      ) : (
        <div className="space-y-3">{rows.map((c) => <Card key={c.id} c={c} />)}</div>
      )}
    </div>
  );
}

function Card({ c }: { c: Confirmation }) {
  const decide = useDecideConfirmation();
  const cancel = useCancelConfirmation();
  const pending = c.status === "pending";
  const busy = decide.isPending || cancel.isPending;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900">{c.staff_name || "—"}</h3>
            {c.employment_status && <span className="badge bg-slate-100 text-slate-500 border-slate-200 capitalize">{c.employment_status}</span>}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {fmt(c.probation_start) && `Probation from ${fmt(c.probation_start)}`}
            {fmt(c.due_date) && ` · due ${fmt(c.due_date)}`}
          </p>
        </div>
        <span className={cn("badge capitalize", STATUS_STYLE[c.status] ?? STATUS_STYLE.pending)}>{c.status}</span>
      </div>
      {c.recommendation && <p className="text-sm text-slate-600 mb-2">{c.recommendation}</p>}
      {!pending && c.notes && <p className="text-xs text-slate-400">Note: {c.notes}{fmt(c.decided_at) ? ` · ${fmt(c.decided_at)}` : ""}</p>}

      {pending && (
        <div className="flex items-center gap-2 mt-3">
          <button onClick={() => decide.mutate({ id: c.id, data: { decision: "confirm" } })} disabled={busy} className="btn-primary gap-1.5 py-1.5 text-sm"><Check size={14} /> Confirm</button>
          <button onClick={() => decide.mutate({ id: c.id, data: { decision: "decline" } })} disabled={busy} className="btn-secondary gap-1.5 py-1.5 text-sm"><X size={14} /> Decline</button>
          <button onClick={() => { if (confirm("Cancel this confirmation?")) cancel.mutate(c.id); }} disabled={busy} className="text-slate-400 hover:text-red-600 p-1.5 ml-auto" title="Cancel"><Trash2 size={14} /></button>
        </div>
      )}
    </div>
  );
}
