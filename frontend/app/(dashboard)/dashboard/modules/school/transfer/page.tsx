"use client";

import { useState } from "react";
import {
  useTransfers, useCreateTransfer, useUpdateTransfer,
} from "@/hooks/useEnrollment";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import { UserCog, Plus, X, Loader2, AlertTriangle } from "lucide-react";

const TYPES = ["transfer_out", "withdrawal"];
const STATUSES = ["pending", "completed"];
const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

const EMPTY = {
  student_id: "", transfer_type: "transfer_out", destination_school: "", reason: "", transfer_date: "", status: "pending",
};

export default function TransferPage() {
  const canWrite = useHasPermission("school:students:write");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<"" | "transfer_out" | "withdrawal">("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...EMPTY });

  const { data, isLoading, isError, refetch } = useTransfers({
    ...(statusFilter ? { status: statusFilter } : {}),
    ...(typeFilter ? { transfer_type: typeFilter } : {}),
  });
  const createTransfer = useCreateTransfer();
  const updateTransfer = useUpdateTransfer();

  const reset = () => { setForm({ ...EMPTY }); setShowForm(false); };
  const submit = () => {
    createTransfer.mutate(
      {
        student_id: form.student_id, transfer_type: form.transfer_type,
        destination_school: form.destination_school || null, reason: form.reason || null,
        transfer_date: form.transfer_date || null, status: form.status,
      },
      { onSuccess: reset },
    );
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Students</span><span>/</span><span className="text-brand-600 font-semibold">Transfer Manager</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Transfer Manager</h1>
          <p className="text-slate-500 text-sm mt-0.5">Record student transfers-out and withdrawals.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Transfer</button>}
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-3">
        {/* Type tabs — the Withdrawal tab is Educare's "Withdrawal List" view. */}
        <div className="flex bg-slate-100 rounded-lg p-0.5 shrink-0">
          {([["", "All"], ["transfer_out", "Transfers Out"], ["withdrawal", "Withdrawals"]] as const).map(([val, label]) => (
            <button
              key={val || "all"}
              onClick={() => setTypeFilter(val)}
              className={cn(
                "px-3 py-1.5 text-xs font-semibold rounded-md transition-colors",
                typeFilter === val ? "bg-white shadow text-slate-900" : "text-slate-500 hover:text-slate-700",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">New Transfer</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Student *</label>
              <EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} />
            </div>
            <div>
              <label className="label">Type</label>
              <select value={form.transfer_type} onChange={(e) => setForm({ ...form, transfer_type: e.target.value })} className="input">
                <option value="transfer_out">Transfer out</option><option value="withdrawal">Withdrawal</option>
              </select>
            </div>
            <div><label className="label">Destination School</label><input value={form.destination_school} onChange={(e) => setForm({ ...form, destination_school: e.target.value })} className="input" /></div>
            <div><label className="label">Transfer Date</label><input type="date" value={form.transfer_date} onChange={(e) => setForm({ ...form, transfer_date: e.target.value })} className="input" /></div>
            <div>
              <label className="label">Status</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input capitalize">
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="md:col-span-2"><label className="label">Reason</label><textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="input" rows={2} /></div>
          </div>
          <p className="text-xs text-slate-400 mt-2">A <strong>completed</strong> transfer removes the student from the active roster.</p>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.student_id || createTransfer.isPending} className="btn-primary gap-2">
              {createTransfer.isPending && <Loader2 size={15} className="animate-spin" />} Record
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Student", "Type", "Destination", "Date", "Status", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center">
                <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
                <p className="text-sm font-semibold text-slate-600">Couldn’t load transfers.</p>
                <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
              </td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{t.student_name || t.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 capitalize">{t.transfer_type.replace("_", " ")}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{t.destination_school || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{t.transfer_date ? formatDate(t.transfer_date) : "—"}</td>
                  <td className="px-5 py-4">
                    {canWrite ? (
                      <select value={t.status} onChange={(e) => updateTransfer.mutate({ id: t.id, data: { status: e.target.value } })} className={cn("input py-1 text-xs capitalize w-32 border", STATUS_STYLE[t.status] || "")}>
                        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    ) : <span className={cn("badge capitalize", STATUS_STYLE[t.status] || "")}>{t.status}</span>}
                  </td>
                  <td className="px-5 py-4" />
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400">
                <UserCog size={36} className="mx-auto mb-3 opacity-40" />
                <p className="font-semibold">No transfers recorded yet</p>
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
