"use client";

import { useEffect, useMemo, useState } from "react";
import {
  usePettyCash, useRecordPettyCash, useVoidPettyCash,
  useBudgets, useCreateBudget, useDeleteBudget, useAccounts, useFinanceSettings,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { Wallet, Plus, X, Loader2, Trash2, AlertTriangle, Ban } from "lucide-react";

export default function PettyCashPage() {
  const canWrite = useHasPermission("payments:write");
  const canPost = useHasPermission("payments:post");

  const { data, isLoading, isError, refetch } = usePettyCash();
  const { data: budgets } = useBudgets();
  const { data: accounts } = useAccounts({ active_only: true });
  const record = useRecordPettyCash();
  const voidTxn = useVoidPettyCash();
  const createBudget = useCreateBudget();
  const delBudget = useDeleteBudget();

  const expenseAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "expense"), [accounts]);
  const cashAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset"), [accounts]);

  const { data: defaults } = useFinanceSettings();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ amount: "", expense_account_id: "", cash_account_id: "", description: "", category: "", txn_date: "" });
  const reset = () => {
    setForm({ amount: "", expense_account_id: defaults?.default_expense_account_id || "", cash_account_id: defaults?.default_cash_account_id || "", description: "", category: "", txn_date: "" });
    setShow(false);
  };
  // Pre-fill the Accounts Setup defaults on first load, only where the field is still
  // empty (never override a manual pick); reset() re-seeds them for the next entry.
  useEffect(() => {
    if (!defaults) return;
    setForm((f) => ({
      ...f,
      expense_account_id: f.expense_account_id || defaults.default_expense_account_id || "",
      cash_account_id: f.cash_account_id || defaults.default_cash_account_id || "",
    }));
  }, [defaults]);
  const submit = () => record.mutate({
    amount: Number(form.amount), expense_account_id: form.expense_account_id, cash_account_id: form.cash_account_id,
    description: form.description || null, category: form.category || null, txn_date: form.txn_date || null,
  }, { onSuccess: reset });

  const [budgetForm, setBudgetForm] = useState({ account_id: "", amount: "", period_label: "" });
  const addBudget = () => createBudget.mutate({ account_id: budgetForm.account_id, amount: Number(budgetForm.amount), period_label: budgetForm.period_label || null }, { onSuccess: () => setBudgetForm({ account_id: "", amount: "", period_label: "" }) });

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Petty Cash &amp; Budget</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Petty Cash &amp; Budget</h1>
          <p className="text-slate-500 text-sm mt-0.5">Small disbursements (posted to the ledger) with soft over-budget warnings.</p>
        </div>
        {canPost && <button onClick={() => setShow((s) => !s)} className="btn-primary gap-2"><Plus size={15} /> Record Disbursement</button>}
      </div>

      {/* Budgets */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
        <h2 className="text-sm font-bold text-slate-800 mb-3">Budgets <span className="text-xs font-normal text-slate-400">(soft — overspend warns, never blocks)</span></h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
          {(budgets ?? []).map((b) => {
            const over = b.spent > b.amount;
            return (
              <div key={b.id} className={cn("rounded-lg border p-3", over ? "border-rose-200 bg-rose-50" : "border-slate-200")}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-800">{b.account_name}</span>
                  {canWrite && <button onClick={() => delBudget.mutate(b.id)} className="text-slate-300 hover:text-red-600"><X size={13} /></button>}
                </div>
                <p className={cn("text-xs mt-1", over ? "text-rose-600 font-semibold" : "text-slate-500")}>Spent {b.spent.toFixed(2)} / {b.amount.toFixed(2)}{over ? " — over budget" : ""}</p>
              </div>
            );
          })}
          {(budgets ?? []).length === 0 && <p className="text-xs text-slate-400">No budgets set.</p>}
        </div>
        {canWrite && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2 items-end border-t border-slate-100 pt-3">
            <div><label className="label">Account</label><select value={budgetForm.account_id} onChange={(e) => setBudgetForm({ ...budgetForm, account_id: e.target.value })} className="input"><option value="">Expense account…</option>{expenseAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            <div><label className="label">Amount</label><input type="number" value={budgetForm.amount} onChange={(e) => setBudgetForm({ ...budgetForm, amount: e.target.value })} className="input" /></div>
            <div><label className="label">Period</label><input value={budgetForm.period_label} onChange={(e) => setBudgetForm({ ...budgetForm, period_label: e.target.value })} className="input" placeholder="optional" /></div>
            <button onClick={addBudget} disabled={!budgetForm.account_id || !budgetForm.amount || createBudget.isPending} className="btn-secondary justify-center">Set budget</button>
          </div>
        )}
      </div>

      {show && canPost && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Record Disbursement</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Amount *</label><input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="input" /></div>
            <div><label className="label">Expense Account *</label><select value={form.expense_account_id} onChange={(e) => setForm({ ...form, expense_account_id: e.target.value })} className="input"><option value="">Select…</option>{expenseAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            <div><label className="label">Petty Cash Account *</label><select value={form.cash_account_id} onChange={(e) => setForm({ ...form, cash_account_id: e.target.value })} className="input"><option value="">Select…</option>{cashAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            <div><label className="label">Category</label><input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="input" /></div>
            <div><label className="label">Date</label><input type="date" value={form.txn_date} onChange={(e) => setForm({ ...form, txn_date: e.target.value })} className="input" /></div>
            <div><label className="label">Description</label><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.amount || !form.expense_account_id || !form.cash_account_id || record.isPending} className="btn-primary gap-2">{record.isPending && <Loader2 size={15} className="animate-spin" />}Record</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Date", "Description", "Expense", "Amount", "Status", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load transactions.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((t) => (
                <tr key={t.id} className={cn("hover:bg-slate-50/70", t.status === "void" && "opacity-50")}>
                  <td className="px-5 py-4 text-xs text-slate-500">{t.txn_date ? formatDate(t.txn_date) : formatDate(t.created_at)}</td>
                  <td className="px-5 py-4 text-sm text-slate-700">{t.description || t.category || "—"}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{t.expense_account_name || "—"}</td>
                  <td className="px-5 py-4 text-sm font-semibold text-slate-800">{t.amount.toFixed(2)}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", t.status === "void" ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-emerald-50 text-emerald-700 border-emerald-200")}>{t.status}</span></td>
                  <td className="px-5 py-4">{canPost && t.status !== "void" && <button onClick={() => { if (confirm("Void this disbursement? Its ledger entry will be reversed.")) voidTxn.mutate(t.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700"><Ban size={13} /> Void</button>}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><Wallet size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No petty cash yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
