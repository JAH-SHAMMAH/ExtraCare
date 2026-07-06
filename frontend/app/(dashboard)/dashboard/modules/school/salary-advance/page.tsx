"use client";

import { useMemo, useState } from "react";
import {
  useSalaryAdvances, useCreateSalaryAdvance, useApproveSalaryAdvance,
  useRejectSalaryAdvance, useRepaySalaryAdvance, useDeleteSalaryAdvance, useAccounts,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import {
  HandCoins, Plus, X, Loader2, Trash2, AlertTriangle, CheckCircle2, Ban, ShieldCheck, Wallet,
} from "lucide-react";
import type { SalaryAdvance } from "@/types";

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  approved: "bg-blue-50 text-blue-700 border-blue-200",
  repaid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
};

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function SalaryAdvancePage() {
  const canWrite = useHasPermission("payments:write");
  const canPost = useHasPermission("payments:post");
  const [statusFilter, setStatusFilter] = useState("");
  const [show, setShow] = useState(false);

  const { data: advances, isLoading, isError, refetch } = useSalaryAdvances(statusFilter ? { status: statusFilter } : undefined);
  const { data: accounts } = useAccounts({ active_only: true });
  const create = useCreateSalaryAdvance();
  const approve = useApproveSalaryAdvance();
  const reject = useRejectSalaryAdvance();
  const repay = useRepaySalaryAdvance();
  const del = useDeleteSalaryAdvance();

  const cashAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset"), [accounts]);

  // New request form
  const [form, setForm] = useState({ staff_user_id: "", staff_name: "", amount: "", reason: "" });
  const resetForm = () => { setForm({ staff_user_id: "", staff_name: "", amount: "", reason: "" }); setShow(false); };
  const submit = () => {
    if (!form.staff_user_id || Number(form.amount) <= 0) return;
    create.mutate(
      { staff_user_id: form.staff_user_id, amount: Number(form.amount), reason: form.reason.trim() || null },
      { onSuccess: resetForm },
    );
  };

  // Approve modal (choose disbursement account)
  const [approveTarget, setApproveTarget] = useState<SalaryAdvance | null>(null);
  const [approveCash, setApproveCash] = useState("");
  const doApprove = () => {
    if (!approveTarget) return;
    approve.mutate(
      { id: approveTarget.id, data: approveCash ? { cash_account_id: approveCash } : {} },
      { onSuccess: () => { setApproveTarget(null); setApproveCash(""); } },
    );
  };

  // Repay modal
  const [repayTarget, setRepayTarget] = useState<SalaryAdvance | null>(null);
  const [repayForm, setRepayForm] = useState({ amount: "", method: "payroll", cash_account_id: "" });
  const openRepay = (a: SalaryAdvance) => { setRepayTarget(a); setRepayForm({ amount: String(a.outstanding), method: "payroll", cash_account_id: "" }); };
  const doRepay = () => {
    if (!repayTarget || Number(repayForm.amount) <= 0) return;
    repay.mutate(
      { id: repayTarget.id, data: { amount: Number(repayForm.amount), method: repayForm.method, cash_account_id: repayForm.cash_account_id || null } },
      { onSuccess: () => setRepayTarget(null) },
    );
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Salary Advance</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Salary Advance</h1>
          <p className="text-slate-500 text-sm mt-0.5">Loan a staff member against future pay, then recover it. Every disbursement and repayment posts to the ledger.</p>
        </div>
        {canWrite && <button onClick={() => { resetForm(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Advance</button>}
      </div>

      <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-5">
        <ShieldCheck size={14} />
        Two-person control: an advance cannot be approved by the same person who requested it. Approval disburses cash (Dr Staff Advances / Cr Cash).
      </div>

      <div className="mb-5">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All statuses</option>
          {["pending", "approved", "repaid", "rejected"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Advance Request</h2><button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div><label className="label">Staff member *</label><EntityPicker type="staff" value={form.staff_user_id || null} onChange={(id, label) => setForm({ ...form, staff_user_id: id || "", staff_name: label || "" })} placeholder="Select staff…" /></div>
            <div><label className="label">Amount (₦) *</label><input type="number" min="0" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="input" placeholder="50000" /></div>
            <div><label className="label">Reason</label><input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="input" placeholder="e.g. Rent, medical" /></div>
          </div>
          <div className="flex justify-end gap-3"><button onClick={resetForm} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.staff_user_id || Number(form.amount) <= 0 || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Submit request</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Staff", "Amount", "Repaid", "Outstanding", "Status", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load advances.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : advances && advances.length > 0 ? (
              advances.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{a.staff_name || "—"}{a.reason && <span className="block text-[11px] text-slate-400">{a.reason}</span>}<span className="block text-[11px] text-slate-400">{formatDate(a.created_at)}</span></td>
                  <td className="px-5 py-4 text-sm text-slate-700">{naira(a.amount)}</td>
                  <td className="px-5 py-4 text-sm text-slate-700">{naira(a.amount_repaid)}</td>
                  <td className="px-5 py-4 text-sm font-semibold text-slate-800">{naira(a.outstanding)}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[a.status] || "")}>{a.status}</span></td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1">
                      {a.status === "pending" && canPost && <button onClick={() => { setApproveTarget(a); setApproveCash(""); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><CheckCircle2 size={13} /> Approve</button>}
                      {a.status === "pending" && canPost && <button onClick={() => { if (confirm("Reject this request?")) reject.mutate(a.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Ban size={13} /> Reject</button>}
                      {a.status === "approved" && canPost && <button onClick={() => openRepay(a)} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700 px-2 py-1 rounded hover:bg-brand-50"><Wallet size={13} /> Repay</button>}
                      {(a.status === "pending" || a.status === "rejected") && canWrite && <button onClick={() => { if (confirm("Delete this request?")) del.mutate(a.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><HandCoins size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No salary advances yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Approve modal */}
      {approveTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={() => setApproveTarget(null)}>
          <div className="bg-white rounded-xl border border-slate-200 p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Approve &amp; disburse</h2><button onClick={() => setApproveTarget(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <p className="text-sm text-slate-600 mb-4">Disburse <span className="font-semibold">{naira(approveTarget.amount)}</span> to <span className="font-semibold">{approveTarget.staff_name}</span>. This posts <span className="font-mono text-xs">Dr Staff Advances / Cr Cash</span> to the ledger.</p>
            <label className="label">Disburse from (cash/bank)</label>
            <select value={approveCash} onChange={(e) => setApproveCash(e.target.value)} className="input mb-1">
              <option value="">Auto (first cash/bank account)</option>
              {cashAccts.map((c) => <option key={c.id} value={c.id}>{c.code} {c.name}</option>)}
            </select>
            <p className="text-[11px] text-slate-400 mb-4">Leave on Auto to let the system pick a cash asset account.</p>
            <div className="flex justify-end gap-3"><button onClick={() => setApproveTarget(null)} className="btn-secondary">Cancel</button><button onClick={doApprove} disabled={approve.isPending} className="btn-primary gap-2">{approve.isPending && <Loader2 size={15} className="animate-spin" />}Approve &amp; disburse</button></div>
          </div>
        </div>
      )}

      {/* Repay modal */}
      {repayTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={() => setRepayTarget(null)}>
          <div className="bg-white rounded-xl border border-slate-200 p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Record repayment</h2><button onClick={() => setRepayTarget(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <p className="text-sm text-slate-600 mb-4"><span className="font-semibold">{repayTarget.staff_name}</span> — outstanding <span className="font-semibold">{naira(repayTarget.outstanding)}</span>. Posts <span className="font-mono text-xs">Dr Cash / Cr Staff Advances</span>.</p>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div><label className="label">Amount (₦) *</label><input type="number" min="0" max={repayTarget.outstanding} value={repayForm.amount} onChange={(e) => setRepayForm({ ...repayForm, amount: e.target.value })} className="input" /></div>
              <div><label className="label">Method</label><select value={repayForm.method} onChange={(e) => setRepayForm({ ...repayForm, method: e.target.value })} className="input"><option value="payroll">Payroll deduction</option><option value="cash">Cash</option></select></div>
            </div>
            <label className="label">Into account (cash/bank)</label>
            <select value={repayForm.cash_account_id} onChange={(e) => setRepayForm({ ...repayForm, cash_account_id: e.target.value })} className="input mb-4">
              <option value="">Auto (first cash/bank account)</option>
              {cashAccts.map((c) => <option key={c.id} value={c.id}>{c.code} {c.name}</option>)}
            </select>
            <div className="flex justify-end gap-3"><button onClick={() => setRepayTarget(null)} className="btn-secondary">Cancel</button><button onClick={doRepay} disabled={Number(repayForm.amount) <= 0 || repay.isPending} className="btn-primary gap-2">{repay.isPending && <Loader2 size={15} className="animate-spin" />}Record repayment</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
