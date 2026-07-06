"use client";

import { useMemo, useState } from "react";
import { useWallets, useUpdateWallet, useSpend } from "@/hooks/useWallet";
import { useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { BadgeDollarSign, Loader2, AlertTriangle, ShoppingBag, Search } from "lucide-react";
import type { StudentWallet } from "@/types";

export default function PocketMoneyPage() {
  const canAdmin = useHasPermission("payments:write");   // set daily limits
  const { data, isLoading, isError, refetch } = useWallets();
  const { data: accounts } = useAccounts({ active_only: true });
  const update = useUpdateWallet();
  const spend = useSpend();

  const incomeAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "income"), [accounts]);
  const [search, setSearch] = useState("");
  const [spendFor, setSpendFor] = useState<StudentWallet | null>(null);
  const [form, setForm] = useState({ amount: "", income_account_id: "" });

  const doSpend = () => {
    if (!spendFor) return;
    spend.mutate({ id: spendFor.id, data: { amount: Number(form.amount), income_account_id: form.income_account_id } },
      { onSuccess: () => { setSpendFor(null); setForm({ amount: "", income_account_id: "" }); } });
  };

  const rows = (data?.items ?? []).filter((w) => !search.trim() || (w.student_name || "").toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Operations</span><span>/</span><span className="text-brand-600 font-semibold">PocketMoney</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">PocketMoney</h1>
        <p className="text-slate-500 text-sm mt-0.5">Record spends against a student’s wallet (same balance) and set daily spend limits. No overdraw.</p>
      </div>

      <div className="relative mb-5 max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find a student…" className="input pl-9" />
      </div>

      {spendFor && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setSpendFor(null)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Spend — {spendFor.student_name}</h3><p className="text-xs text-slate-400 mt-0.5">Balance {spendFor.balance.toFixed(2)}{spendFor.spend_limit_daily != null ? ` · daily limit ${spendFor.spend_limit_daily.toFixed(2)}` : ""}</p></div>
            <div className="px-6 py-4 grid grid-cols-1 gap-4">
              <div><label className="label">Amount *</label><input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="input" /></div>
              <div><label className="label">Sold as (income) *</label><select value={form.income_account_id} onChange={(e) => setForm({ ...form, income_account_id: e.target.value })} className="input"><option value="">Select…</option>{incomeAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setSpendFor(null)} className="btn-secondary">Cancel</button><button onClick={doSpend} disabled={!form.amount || !form.income_account_id || spend.isPending} className="btn-primary gap-2">{spend.isPending && <Loader2 size={15} className="animate-spin" />}Record spend</button></div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Balance", "Daily limit", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 4 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={4} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load wallets.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows.length > 0 ? (
              rows.map((w) => (
                <tr key={w.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{w.student_name || w.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm font-bold text-slate-900">{w.balance.toFixed(2)}</td>
                  <td className="px-5 py-4">
                    {canAdmin ? (
                      <input
                        type="number" defaultValue={w.spend_limit_daily ?? ""} placeholder="none"
                        onBlur={(e) => { const v = e.target.value; update.mutate({ id: w.id, data: { spend_limit_daily: v ? Number(v) : null } }); }}
                        className="input py-1 text-xs w-28"
                      />
                    ) : (w.spend_limit_daily != null ? w.spend_limit_daily.toFixed(2) : "—")}
                  </td>
                  <td className="px-5 py-4">
                    <button onClick={() => { setSpendFor(w); setForm({ amount: "", income_account_id: "" }); }} disabled={!w.is_active} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700 px-2 py-1 rounded hover:bg-brand-50 disabled:opacity-40"><ShoppingBag size={13} /> Spend</button>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={4} className="py-16 text-center text-slate-400"><BadgeDollarSign size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No wallets yet</p><p className="text-sm mt-1">Create wallets in Wallet Manager first.</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
