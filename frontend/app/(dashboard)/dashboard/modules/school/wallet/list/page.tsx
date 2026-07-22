"use client";

import { useMemo, useState } from "react";
import {
  useWallets, useWallet, useCreateWallet, useTopUp, useWithdraw, useWalletReconciliation,
} from "@/hooks/useWallet";
import { useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatCurrency } from "@/lib/utils";
import {
  Wallet, Plus, X, Loader2, AlertTriangle, Scale, ArrowDownLeft, ArrowUpRight, Receipt, RotateCcw,
} from "lucide-react";
import type { StudentWallet } from "@/types";

const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—");
const KIND_LABEL: Record<string, string> = { top_up: "Credit", spend: "Spend", withdrawal: "Withdrawal" };

export default function WalletListPage() {
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
  const [detailId, setDetailId] = useState<string | null>(null);
  const { data: detail, isLoading: detailLoading } = useWallet(detailId);

  const doMove = () => {
    if (!move) return;
    const payload = { amount: Number(moveForm.amount), cash_account_id: moveForm.cash_account_id };
    const onDone = { onSuccess: () => { setMove(null); setMoveForm({ amount: "", cash_account_id: "" }); } };
    if (move.kind === "topup") topup.mutate({ id: move.wallet.id, data: payload }, onDone);
    else withdraw.mutate({ id: move.wallet.id, data: payload }, onDone);
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Wallet Manager</span><span>/</span><span className="text-brand-600 font-semibold">Wallet List</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Wallet List</h1>
          <p className="text-slate-500 text-sm mt-0.5">Each student’s cashless account with its funding parent — Add Credit, withdraw, or view history.</p>
        </div>
        {canWrite && <button onClick={() => setShowNew((s) => !s)} className="btn-primary gap-2"><Plus size={15} /> New Wallet</button>}
      </div>

      {recon && (
        <div className={cn("flex items-center gap-2 text-xs rounded-lg px-3 py-2 mb-5 border", recon.balanced ? "text-emerald-700 bg-emerald-50 border-emerald-200" : "text-rose-700 bg-rose-50 border-rose-200")}>
          <Scale size={14} />
          Reconciliation: GL float {formatCurrency(recon.gl_balance)} vs wallet balances {formatCurrency(recon.subledger_total)} — {recon.balanced ? "balanced ✓" : "OUT OF BALANCE"}
        </div>
      )}

      {showNew && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div><label className="label">Student *</label><EntityPicker type="student" value={studentId || null} onChange={(id) => setStudentId(id || "")} /></div>
          <div><label className="label">Daily Spend Limit (PocketMoney)</label><input type="number" value={limit} onChange={(e) => setLimit(e.target.value)} className="input" placeholder="uses org default if blank" /></div>
          <button onClick={() => create.mutate({ student_id: studentId, spend_limit_daily: limit ? Number(limit) : null }, { onSuccess: () => { setStudentId(""); setLimit(""); setShowNew(false); } })} disabled={!studentId || create.isPending} className="btn-primary gap-2 justify-center">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create wallet</button>
        </div>
      )}

      {move && canPost && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setMove(null)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">{move.kind === "topup" ? "Add Credit" : "Withdraw"} — {move.wallet.student_name}</h3><button onClick={() => setMove(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
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
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Parent / Guardian", "Class", "Balance", "Daily limit", "Status", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 7 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={7} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load wallets.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((w) => (
                <tr key={w.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800 whitespace-nowrap">{w.student_name || w.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 whitespace-nowrap">{w.guardian_name || <span className="text-slate-300">—</span>}{w.guardian_phone && <span className="block text-xs text-slate-400">{w.guardian_phone}</span>}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 whitespace-nowrap">{w.class_name || <span className="text-slate-300">—</span>}</td>
                  <td className="px-5 py-4 text-sm font-bold text-slate-900 whitespace-nowrap">{formatCurrency(w.balance)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 whitespace-nowrap">{w.spend_limit_daily != null ? formatCurrency(w.spend_limit_daily) : "—"}</td>
                  <td className="px-5 py-4"><span className={cn("badge", w.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{w.is_active ? "Active" : "Inactive"}</span></td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1">
                      {canPost && <button onClick={() => { setMove({ wallet: w, kind: "topup" }); setMoveForm({ amount: "", cash_account_id: "" }); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><ArrowDownLeft size={13} /> Add Credit</button>}
                      {canPost && <button onClick={() => { setMove({ wallet: w, kind: "withdraw" }); setMoveForm({ amount: "", cash_account_id: "" }); }} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-100"><ArrowUpRight size={13} /> Withdraw</button>}
                      <button onClick={() => setDetailId(w.id)} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700 px-2 py-1 rounded hover:bg-brand-50"><Receipt size={13} /> Details</button>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={7} className="py-16 text-center text-slate-400"><Wallet size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No wallets yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Details drawer — wallet history */}
      {detailId && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex justify-end" onClick={() => setDetailId(null)}>
          <div className="bg-white w-full max-w-md h-full shadow-xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 sticky top-0 bg-white">
              <div><h3 className="text-sm font-bold text-slate-800">{detail?.student_name || "Wallet"}</h3><p className="text-xs text-slate-400">{detail?.guardian_name ? `Parent: ${detail.guardian_name}` : "Transaction history"}</p></div>
              <button onClick={() => setDetailId(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            {detailLoading || !detail ? (
              <div className="p-6 space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />)}</div>
            ) : (
              <div className="p-6">
                <div className="rounded-xl bg-slate-50 border border-slate-100 p-4 mb-4 flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Balance</span>
                  <span className="text-lg font-black text-slate-900">{formatCurrency(detail.balance)}</span>
                </div>
                {detail.entries.length === 0 ? (
                  <p className="text-sm text-slate-400 text-center py-10">No transactions yet.</p>
                ) : (
                  <div className="divide-y divide-slate-50">
                    {detail.entries.map((e) => (
                      <div key={e.id} className={cn("flex items-center gap-3 py-3", e.reversed && "opacity-50")}>
                        <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center shrink-0", e.signed_amount >= 0 ? "bg-emerald-50 text-emerald-600" : "bg-rose-50 text-rose-600")}>
                          {e.signed_amount >= 0 ? <ArrowDownLeft size={14} /> : <ArrowUpRight size={14} />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold text-slate-700">{KIND_LABEL[e.kind] || e.kind}{e.reversed && <span className="ml-2 inline-flex items-center gap-0.5 text-[10px] font-bold text-rose-500"><RotateCcw size={10} /> reversed</span>}</p>
                          <p className="text-xs text-slate-400 truncate">{fmtDate(e.created_at)}{e.memo ? ` · ${e.memo}` : ""}</p>
                        </div>
                        <span className={cn("text-sm font-bold whitespace-nowrap", e.signed_amount >= 0 ? "text-emerald-600" : "text-rose-600")}>{e.signed_amount >= 0 ? "+" : ""}{formatCurrency(e.signed_amount)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
