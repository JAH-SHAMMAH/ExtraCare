"use client";

import { useEffect, useMemo, useState } from "react";
import {
  usePayrollRuns, useCreatePayroll, useApprovePayroll, useVoidPayroll, useDeletePayroll, useAccounts,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { PrintLetterhead } from "@/components/branding/Brand";
import { cn, formatDate } from "@/lib/utils";
import { BadgeDollarSign, Plus, X, Loader2, Trash2, AlertTriangle, CheckCircle2, Ban, ShieldCheck, Printer } from "lucide-react";
import type { PayrollRun } from "@/types";

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-50 text-slate-500 border-slate-200",
  posted: "bg-emerald-50 text-emerald-700 border-emerald-200",
  void: "bg-rose-50 text-rose-700 border-rose-200",
};

type SlipDraft = { staff_user_id: string; staff_name: string; gross: string; deductions: string };

export default function PayrollPage() {
  const canWrite = useHasPermission("payments:write");
  const canPost = useHasPermission("payments:post");
  const [statusFilter, setStatusFilter] = useState("");
  const [show, setShow] = useState(false);

  const { data, isLoading, isError, refetch } = usePayrollRuns(statusFilter ? { status: statusFilter } : undefined);
  const { data: accounts } = useAccounts({ active_only: true });
  const create = useCreatePayroll();
  const approve = useApprovePayroll();
  const voidRun = useVoidPayroll();
  const del = useDeletePayroll();

  const expenseAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "expense"), [accounts]);
  const settleAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset" || a.type === "liability"), [accounts]);

  const [form, setForm] = useState({ period_label: "", run_date: "", expense_account_id: "", net_account_id: "", deductions_account_id: "" });
  const [slips, setSlips] = useState<SlipDraft[]>([{ staff_user_id: "", staff_name: "", gross: "", deductions: "0" }]);

  const reset = () => {
    setForm({ period_label: "", run_date: "", expense_account_id: "", net_account_id: "", deductions_account_id: "" });
    setSlips([{ staff_user_id: "", staff_name: "", gross: "", deductions: "0" }]);
    setShow(false);
  };
  const submit = () => {
    const cleaned = slips.filter((s) => (s.staff_name.trim() || s.staff_user_id) && Number(s.gross) > 0).map((s) => ({
      staff_user_id: s.staff_user_id || null, staff_name: s.staff_name || null,
      gross: Number(s.gross) || 0, deductions: Number(s.deductions) || 0,
    }));
    if (cleaned.length === 0) return;
    create.mutate({
      period_label: form.period_label.trim(), run_date: form.run_date || null,
      expense_account_id: form.expense_account_id, net_account_id: form.net_account_id,
      deductions_account_id: form.deductions_account_id || null, payslips: cleaned,
    }, { onSuccess: reset });
  };

  // Branded payslips → browser print / Save-as-PDF (one page per staff member).
  const [printRun, setPrintRun] = useState<PayrollRun | null>(null);
  useEffect(() => {
    if (!printRun) return;
    const clear = () => setPrintRun(null);
    window.addEventListener("afterprint", clear);
    window.print();
    return () => window.removeEventListener("afterprint", clear);
  }, [printRun]);

  const rows = data?.items;

  return (
    <>
    <div className="p-8 max-w-6xl mx-auto no-print">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Payroll</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Payroll</h1>
          <p className="text-slate-500 text-sm mt-0.5">Draft a run, then a different authoriser approves + posts it.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Run</button>}
      </div>

      <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-5">
        <ShieldCheck size={14} />
        Two-person control: a payroll run cannot be approved by the same person who created it.
      </div>

      <div className="mb-5">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize"><option value="">All statuses</option>{["draft", "posted", "void"].map((s) => <option key={s} value={s}>{s}</option>)}</select>
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Payroll Run (draft)</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div><label className="label">Period *</label><input value={form.period_label} onChange={(e) => setForm({ ...form, period_label: e.target.value })} className="input" placeholder="January 2026" /></div>
            <div><label className="label">Run Date</label><input type="date" value={form.run_date} onChange={(e) => setForm({ ...form, run_date: e.target.value })} className="input" /></div>
            <div><label className="label">Salary Expense *</label><select value={form.expense_account_id} onChange={(e) => setForm({ ...form, expense_account_id: e.target.value })} className="input"><option value="">Select…</option>{expenseAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            <div><label className="label">Net Pay (Cash/Payable) *</label><select value={form.net_account_id} onChange={(e) => setForm({ ...form, net_account_id: e.target.value })} className="input"><option value="">Select…</option>{settleAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            <div><label className="label">Deductions Payable</label><select value={form.deductions_account_id} onChange={(e) => setForm({ ...form, deductions_account_id: e.target.value })} className="input"><option value="">— (optional)</option>{settleAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
          </div>
          <label className="label">Payslips</label>
          <div className="space-y-2 mb-3">
            {slips.map((s, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-center">
                <div className="col-span-5"><EntityPicker type="staff" value={s.staff_user_id || null} onChange={(id, label) => setSlips(slips.map((x, j) => j === i ? { ...x, staff_user_id: id || "", staff_name: label || x.staff_name } : x))} placeholder="Staff member…" /></div>
                <input type="number" value={s.gross} onChange={(e) => setSlips(slips.map((x, j) => j === i ? { ...x, gross: e.target.value } : x))} className="input col-span-3" placeholder="Gross" />
                <input type="number" value={s.deductions} onChange={(e) => setSlips(slips.map((x, j) => j === i ? { ...x, deductions: e.target.value } : x))} className="input col-span-3" placeholder="Deductions" />
                <button onClick={() => setSlips(slips.filter((_, j) => j !== i))} className="col-span-1 text-slate-400 hover:text-red-600"><X size={15} /></button>
              </div>
            ))}
          </div>
          <button onClick={() => setSlips([...slips, { staff_user_id: "", staff_name: "", gross: "", deductions: "0" }])} className="text-xs font-semibold text-brand-600 hover:text-brand-700 mb-4">+ Add payslip</button>
          <div className="flex justify-end gap-3"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.period_label.trim() || !form.expense_account_id || !form.net_account_id || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Save draft</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Period", "Gross", "Net", "Status", "Approved by", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load payroll.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((run) => (
                <tr key={run.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{run.period_label}<span className="block text-[11px] text-slate-400">{run.payslips.length} payslip(s)</span></td>
                  <td className="px-5 py-4 text-sm text-slate-700">{run.total_gross.toFixed(2)}</td>
                  <td className="px-5 py-4 text-sm font-semibold text-slate-800">{run.total_net.toFixed(2)}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[run.status] || "")}>{run.status}</span></td>
                  <td className="px-5 py-4 text-xs text-slate-500">{run.approved_at ? formatDate(run.approved_at) : "—"}</td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1">
                      <button onClick={() => setPrintRun(run)} title="Print payslips / save as PDF" className="text-slate-400 hover:text-brand-600 p-1"><Printer size={14} /></button>
                      {run.status === "draft" && canPost && <button onClick={() => approve.mutate(run.id)} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><CheckCircle2 size={13} /> Approve</button>}
                      {run.status === "draft" && canWrite && <button onClick={() => { if (confirm("Delete draft run?")) del.mutate(run.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
                      {run.status === "posted" && canPost && <button onClick={() => { if (confirm("Void this run? Its ledger entry will be reversed.")) voidRun.mutate(run.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Ban size={13} /> Void</button>}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><BadgeDollarSign size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No payroll runs yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
    <PrintablePayrollRun run={printRun} />
    </>
  );
}

/** Print-only branded payslips — one letterhead'd page per staff member in the
 *  run, so each person keeps their own document. Hidden on screen. */
function PrintablePayrollRun({ run }: { run: PayrollRun | null }) {
  if (!run) return null;
  return (
    <div className="print-only">
      {run.payslips.map((p, i) => (
        <section key={p.id || i} className={cn("p-2 text-slate-900", i < run.payslips.length - 1 && "break-after-page")}>
          <PrintLetterhead title="Payslip" subtitle={run.period_label} />
          <div className="flex justify-between mb-6 text-sm">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Staff member</p>
              <p className="font-semibold">{p.staff_name || "—"}</p>
            </div>
            <div className="text-right">
              <p><span className="text-slate-400">Period: </span>{run.period_label}</p>
              {run.run_date && <p><span className="text-slate-400">Run date: </span>{formatDate(run.run_date)}</p>}
            </div>
          </div>
          <table className="w-full text-left text-sm">
            <tbody>
              <tr className="border-b border-slate-100"><td className="py-2 text-slate-500">Gross pay</td><td className="py-2 text-right font-medium">{p.gross.toFixed(2)}</td></tr>
              <tr className="border-b border-slate-100"><td className="py-2 text-slate-500">Deductions</td><td className="py-2 text-right font-medium">({p.deductions.toFixed(2)})</td></tr>
              <tr className="border-t-2 border-slate-300"><td className="py-2 font-bold uppercase tracking-wide text-slate-600">Net pay</td><td className="py-2 text-right text-lg font-black">{p.net.toFixed(2)}</td></tr>
            </tbody>
          </table>
          {p.notes && <p className="mt-6 text-xs text-slate-500">{p.notes}</p>}
        </section>
      ))}
    </div>
  );
}
