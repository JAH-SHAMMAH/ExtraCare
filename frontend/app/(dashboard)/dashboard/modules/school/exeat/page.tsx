"use client";

import { useState } from "react";
import {
  useExeats, useCreateExeat, useApproveExeat, useRejectExeat, useReturnExeat,
} from "@/hooks/usePastoral";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import { Loader2, Plus, X, AlertTriangle, FileText, Check, Ban, LogIn } from "lucide-react";

const STATUSES = ["pending", "approved", "rejected", "returned"];
const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
  returned: "bg-slate-50 text-slate-500 border-slate-200",
};

export default function ExeatPage() {
  const canRequest = useHasPermission("school:hostel:write");
  const canApprove = useHasPermission("school_admin:write");   // explicit approver tier
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ student_id: "", reason: "", destination: "", depart_at: "", expected_return_at: "" });

  const { data, isLoading, isError, refetch } = useExeats(statusFilter ? { status: statusFilter } : undefined);
  const create = useCreateExeat();
  const approve = useApproveExeat();
  const reject = useRejectExeat();
  const markReturned = useReturnExeat();

  const reset = () => { setForm({ student_id: "", reason: "", destination: "", depart_at: "", expected_return_at: "" }); setShowForm(false); };
  const submit = () => create.mutate(
    {
      student_id: form.student_id, reason: form.reason || null, destination: form.destination || null,
      depart_at: form.depart_at || null, expected_return_at: form.expected_return_at || null,
    },
    { onSuccess: reset },
  );

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral &amp; Welfare</span><span>/</span><span className="text-brand-600 font-semibold">Exeat Requests</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Exeat Requests</h1>
          <p className="text-slate-500 text-sm mt-0.5">Permission for a boarder to leave campus. {canApprove ? "You can authorise requests." : "Authorisation is restricted to approvers."}</p>
        </div>
        {canRequest && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Request</button>}
      </div>

      <div className="mb-5">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize"><option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
      </div>

      {showForm && canRequest && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Exeat Request</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>
            <div><label className="label">Destination</label><input value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} className="input" /></div>
            <div><label className="label">Depart</label><input type="datetime-local" value={form.depart_at} onChange={(e) => setForm({ ...form, depart_at: e.target.value })} className="input" /></div>
            <div><label className="label">Expected Return</label><input type="datetime-local" value={form.expected_return_at} onChange={(e) => setForm({ ...form, expected_return_at: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Reason</label><textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.student_id || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Submit</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Destination", "Depart", "Status", "Approved by", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load exeat requests.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((e) => (
                <tr key={e.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{e.student_name || e.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{e.destination || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{e.depart_at ? formatDate(e.depart_at) : "—"}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[e.status] || "")}>{e.status}</span></td>
                  <td className="px-5 py-4 text-xs text-slate-500">{e.approved_by_name || "—"}{e.decided_at ? ` · ${formatDate(e.decided_at)}` : ""}</td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1">
                      {e.status === "pending" && canApprove && (
                        <>
                          <button onClick={() => { const note = prompt("Approval note (optional):") ?? undefined; approve.mutate({ id: e.id, data: note ? { decision_note: note } : undefined }); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><Check size={13} /> Approve</button>
                          <button onClick={() => { const note = prompt("Reason for rejection:") ?? undefined; reject.mutate({ id: e.id, data: note ? { decision_note: note } : undefined }); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Ban size={13} /> Reject</button>
                        </>
                      )}
                      {e.status === "pending" && !canApprove && <span className="text-[11px] text-slate-400 italic">awaiting approver</span>}
                      {e.status === "approved" && canRequest && (
                        <button onClick={() => markReturned.mutate(e.id)} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700 px-2 py-1 rounded hover:bg-brand-50"><LogIn size={13} /> Mark returned</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><FileText size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No exeat requests yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
