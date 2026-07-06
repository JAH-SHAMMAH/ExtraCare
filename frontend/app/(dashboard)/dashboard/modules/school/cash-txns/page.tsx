"use client";

import { useMemo, useState } from "react";
import { useCashTxns, useRecordCash, useVoidCash, useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { DollarSign, Plus, X, Loader2, AlertTriangle, Ban, ArrowDownLeft, ArrowUpRight } from "lucide-react";

export default function CashTransactionsPage() {
  const canPost = useHasPermission("payments:post");
  const [typeFilter, setTypeFilter] = useState("");
  const [show, setShow] = useState(false);

  const { data, isLoading, isError, refetch } = useCashTxns(typeFilter ? { type: typeFilter } : undefined);
  const { data: accounts } = useAccounts({ active_only: true });
  const record = useRecordCash();
  const voidTxn = useVoidCash();

  const cashAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset"), [accounts]);
  const counterAccts = useMemo(() => (accounts ?? []).filter((a) => a.type !== "asset"), [accounts]);

  const [form, setForm] = useState({ type: "receipt", amount: "", cash_account_id: "", counter_account_id: "", counterparty: "", description: "", txn_date: "" });
  const reset = () => { setForm({ type: "receipt", amount: "", cash_account_id: "", counter_account_id: "", counterparty: "", description: "", txn_date: "" }); setShow(false); };
  const submit = () => record.mutate({
    type: form.type, amount: Number(form.amount), cash_account_id: form.cash_account_id, counter_account_id: form.counter_account_id,
    counterparty: form.counterparty || null, description: form.description || null, txn_date: form.txn_date || null,
  }, { onSuccess: reset });

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Cash Transactions</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Cash Transactions</h1>
          <p className="text-slate-500 text-sm mt-0.5">Cash receipts and payments, posted straight to the ledger.</p>
        </div>
        {canPost && <button onClick={() => setShow((s) => !s)} className="btn-primary gap-2"><Plus size={15} /> New Transaction</button>}
      </div>

      <div className="mb-5">
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="input max-w-[180px] capitalize"><option value="">All types</option><option value="receipt">Receipt</option><option value="payment">Payment</option></select>
      </div>

      {show && canPost && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Cash Transaction</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Type *</label><select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="input"><option value="receipt">Receipt (money in)</option><option value="payment">Payment (money out)</option></select></div>
            <div><label className="label">Amount *</label><input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="input" /></div>
            <div><label className="label">Cash Account *</label><select value={form.cash_account_id} onChange={(e) => setForm({ ...form, cash_account_id: e.target.value })} className="input"><option value="">Select…</option>{cashAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            <div><label className="label">{form.type === "receipt" ? "Income / source" : "Expense / payee"} account *</label><select value={form.counter_account_id} onChange={(e) => setForm({ ...form, counter_account_id: e.target.value })} className="input"><option value="">Select…</option>{counterAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name} ({a.type})</option>)}</select></div>
            <div><label className="label">Counterparty</label><input value={form.counterparty} onChange={(e) => setForm({ ...form, counterparty: e.target.value })} className="input" /></div>
            <div><label className="label">Date</label><input type="date" value={form.txn_date} onChange={(e) => setForm({ ...form, txn_date: e.target.value })} className="input" /></div>
            <div className="md:col-span-3"><label className="label">Description</label><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.amount || !form.cash_account_id || !form.counter_account_id || record.isPending} className="btn-primary gap-2">{record.isPending && <Loader2 size={15} className="animate-spin" />}Record</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Date", "Type", "Counterparty", "Amount", "Status", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load transactions.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((t) => (
                <tr key={t.id} className={cn("hover:bg-slate-50/70", t.status === "void" && "opacity-50")}>
                  <td className="px-5 py-4 text-xs text-slate-500">{t.txn_date ? formatDate(t.txn_date) : formatDate(t.created_at)}</td>
                  <td className="px-5 py-4">
                    <span className={cn("inline-flex items-center gap-1 text-xs font-semibold", t.type === "receipt" ? "text-emerald-600" : "text-rose-600")}>
                      {t.type === "receipt" ? <ArrowDownLeft size={13} /> : <ArrowUpRight size={13} />}{t.type}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-sm text-slate-700">{t.counterparty || t.description || "—"}</td>
                  <td className="px-5 py-4 text-sm font-semibold text-slate-800">{t.amount.toFixed(2)}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", t.status === "void" ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-emerald-50 text-emerald-700 border-emerald-200")}>{t.status}</span></td>
                  <td className="px-5 py-4">{canPost && t.status !== "void" && <button onClick={() => { if (confirm("Void this transaction? Its ledger entry will be reversed.")) voidTxn.mutate(t.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700"><Ban size={13} /> Void</button>}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><DollarSign size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No cash transactions yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
