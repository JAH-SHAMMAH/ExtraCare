"use client";

import { useMemo, useState } from "react";
import {
  useWallets, useCreateWallet, useTopUp, useWithdraw, useWalletReconciliation,
} from "@/hooks/useWallet";
import { useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { Wallet, Plus, X, Loader2, AlertTriangle, Scale, ArrowDownLeft, ArrowUpRight } from "lucide-react";
import type { StudentWallet } from "@/types";

export default function WalletManagerPage() {
  const canPost = useHasPermission("payments:post");
  const canWrite = useHasPermission("payments:write");

  const { data, isLoading, isError, refetch } = useWallets();
  const { data: recon } = useWalletReconciliation();
  const { data: accounts } = useAccounts({ active_only: true });
  const create = useCreateWallet();
  const topup = useTopUp();
  const withdraw = useWithdraw();

  const cashAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset"), [accounts]);

  const [showNew, setShowNew] = useState(false);
  const [studentId, setStudentId] = useState("");
  const [limit, setLimit] = useState("");

  const [move, setMove] = useState<{ wallet: StudentWallet; kind: "topup" | "withdraw" } | null>(null);
  const [moveForm, setMoveForm] = useState({ amount: "", cash_account_id: "" });

  const doMove = () => {
    if (!move) return;
    const data = { amount: Number(moveForm.amount), cash_account_id: moveForm.cash_account_id };
    const onDone = { onSuccess: () => { setMove(null); setMoveForm({ amount: "", cash_account_id: "" }); } };
    if (move.kind === "topup") topup.mutate({ id: move.wallet.id, data }, onDone);
    else withdraw.mutate({ id: move.wallet.id, data }, onDone);
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Operations</span><span>/</span><span className="text-brand-600 font-semibold">Wallet Manager</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Wallet Manager</h1>
          <p className="text-slate-500 text-sm mt-0.5">Student cashless accounts — funds held as a liability; balances derived from the ledger.</p>
        </div>
        {canWrite && <button onClick={() => setShowNew((s) => !s)} className="btn-primary gap-2"><Plus size={15} /> New Wallet</button>}
      </div>

      {recon && (
        <div className={cn("flex items-center gap-2 text-xs rounded-lg px-3 py-2 mb-5 border", recon.balanced ? "text-emerald-700 bg-emerald-50 border-emerald-200" : "text-rose-700 bg-rose-50 border-rose-200")}>
          <Scale size={14} />
          Reconciliation: GL float {recon.gl_balance.toFixed(2)} vs wallet balances {recon.subledger_total.toFixed(2)} — {recon.balanced ? "balanced ✓" : "OUT OF BALANCE"}
        </div>
      )}

      {showNew && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div><label className="label">Student *</label><EntityPicker type="student" value={studentId || null} onChange={(id) => setStudentId(id || "")} /></div>
          <div><label className="label">Daily Spend Limit (PocketMoney)</label><input type="number" value={limit} onChange={(e) => setLimit(e.target.value)} className="input" placeholder="optional" /></div>
          <button onClick={() => create.mutate({ student_id: studentId, spend_limit_daily: limit ? Number(limit) : null }, { onSuccess: () => { setStudentId(""); setLimit(""); setShowNew(false); } })} disabled={!studentId || create.isPending} className="btn-primary gap-2 justify-center">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create wallet</button>
        </div>
      )}

      {move && canPost && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setMove(null)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800 capitalize">{move.kind} — {move.wallet.student_name}</h3><button onClick={() => setMove(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 grid grid-cols-1 gap-4">
              <div><label className="label">Amount *</label><input type="number" value={moveForm.amount} onChange={(e) => setMoveForm({ ...moveForm, amount: e.target.value })} className="input" /></div>
              <div><label className="label">{move.kind === "topup" ? "Funded into" : "Paid from"} cash account *</label><select value={moveForm.cash_account_id} onChange={(e) => setMoveForm({ ...moveForm, cash_account_id: e.target.value })} className="input"><option value="">Select…</option>{cashAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setMove(null)} className="btn-secondary">Cancel</button><button onClick={doMove} disabled={!moveForm.amount || !moveForm.cash_account_id || topup.isPending || withdraw.isPending} className="btn-primary gap-2">{(topup.isPending || withdraw.isPending) && <Loader2 size={15} className="animate-spin" />}Confirm</button></div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Daily limit", "Balance", "Status", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 5 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={5} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load wallets.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((w) => (
                <tr key={w.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{w.student_name || w.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{w.spend_limit_daily != null ? w.spend_limit_daily.toFixed(2) : "—"}</td>
                  <td className="px-5 py-4 text-sm font-bold text-slate-900">{w.balance.toFixed(2)}</td>
                  <td className="px-5 py-4"><span className={cn("badge", w.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{w.is_active ? "Active" : "Inactive"}</span></td>
                  <td className="px-5 py-4">
                    {canPost && (
                      <div className="flex items-center gap-1">
                        <button onClick={() => { setMove({ wallet: w, kind: "topup" }); setMoveForm({ amount: "", cash_account_id: "" }); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><ArrowDownLeft size={13} /> Top-up</button>
                        <button onClick={() => { setMove({ wallet: w, kind: "withdraw" }); setMoveForm({ amount: "", cash_account_id: "" }); }} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-100"><ArrowUpRight size={13} /> Withdraw</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={5} className="py-16 text-center text-slate-400"><Wallet size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No wallets yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
