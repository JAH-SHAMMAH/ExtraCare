"use client";

import { useMemo, useState } from "react";
import {
  useCoopMembers, useCreateMember, useContribute, usePayout, useCoopReconciliation,
} from "@/hooks/useWallet";
import { useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Handshake, Plus, X, Loader2, AlertTriangle, Scale, ArrowDownLeft, ArrowUpRight } from "lucide-react";
import type { CooperativeMember } from "@/types";

export default function CooperativePage() {
  const canPost = useHasPermission("payments:post");
  const canWrite = useHasPermission("payments:write");

  const { data, isLoading, isError, refetch } = useCoopMembers();
  const { data: recon } = useCoopReconciliation();
  const { data: accounts } = useAccounts({ active_only: true });
  const create = useCreateMember();
  const contribute = useContribute();
  const payout = usePayout();

  const cashAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset"), [accounts]);

  const [showNew, setShowNew] = useState(false);
  const [name, setName] = useState("");
  const [move, setMove] = useState<{ member: CooperativeMember; kind: "contribute" | "payout" } | null>(null);
  const [moveForm, setMoveForm] = useState({ amount: "", cash_account_id: "" });

  const doMove = () => {
    if (!move) return;
    const data = { amount: Number(moveForm.amount), cash_account_id: moveForm.cash_account_id };
    const onDone = { onSuccess: () => { setMove(null); setMoveForm({ amount: "", cash_account_id: "" }); } };
    if (move.kind === "contribute") contribute.mutate({ id: move.member.id, data }, onDone);
    else payout.mutate({ id: move.member.id, data }, onDone);
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Operations</span><span>/</span><span className="text-brand-600 font-semibold">Cooperative</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Cooperative</h1>
          <p className="text-slate-500 text-sm mt-0.5">Member savings held on their behalf (a liability) — contributions &amp; payouts, ledger-backed.</p>
        </div>
        {canWrite && <button onClick={() => setShowNew((s) => !s)} className="btn-primary gap-2"><Plus size={15} /> New Member</button>}
      </div>

      {recon && (
        <div className={cn("flex items-center gap-2 text-xs rounded-lg px-3 py-2 mb-5 border", recon.balanced ? "text-emerald-700 bg-emerald-50 border-emerald-200" : "text-rose-700 bg-rose-50 border-rose-200")}>
          <Scale size={14} />
          Reconciliation: GL fund {recon.gl_balance.toFixed(2)} vs member balances {recon.subledger_total.toFixed(2)} — {recon.balanced ? "balanced ✓" : "OUT OF BALANCE"}
        </div>
      )}

      {showNew && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div className="md:col-span-2"><label className="label">Member Name *</label><input value={name} onChange={(e) => setName(e.target.value)} className="input" /></div>
          <button onClick={() => create.mutate({ member_name: name.trim() }, { onSuccess: () => { setName(""); setShowNew(false); } })} disabled={!name.trim() || create.isPending} className="btn-primary gap-2 justify-center">{create.isPending && <Loader2 size={15} className="animate-spin" />}Add member</button>
        </div>
      )}

      {move && canPost && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setMove(null)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800 capitalize">{move.kind} — {move.member.member_name}</h3><button onClick={() => setMove(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 grid grid-cols-1 gap-4">
              <div><label className="label">Amount *</label><input type="number" value={moveForm.amount} onChange={(e) => setMoveForm({ ...moveForm, amount: e.target.value })} className="input" /></div>
              <div><label className="label">{move.kind === "contribute" ? "Received into" : "Paid from"} cash account *</label><select value={moveForm.cash_account_id} onChange={(e) => setMoveForm({ ...moveForm, cash_account_id: e.target.value })} className="input"><option value="">Select…</option>{cashAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setMove(null)} className="btn-secondary">Cancel</button><button onClick={doMove} disabled={!moveForm.amount || !moveForm.cash_account_id || contribute.isPending || payout.isPending} className="btn-primary gap-2">{(contribute.isPending || payout.isPending) && <Loader2 size={15} className="animate-spin" />}Confirm</button></div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Member", "Balance", "Status", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 4 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={4} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load members.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((m) => (
                <tr key={m.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{m.member_name}</td>
                  <td className="px-5 py-4 text-sm font-bold text-slate-900">{m.balance.toFixed(2)}</td>
                  <td className="px-5 py-4"><span className={cn("badge", m.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{m.is_active ? "Active" : "Inactive"}</span></td>
                  <td className="px-5 py-4">
                    {canPost && (
                      <div className="flex items-center gap-1">
                        <button onClick={() => { setMove({ member: m, kind: "contribute" }); setMoveForm({ amount: "", cash_account_id: "" }); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><ArrowDownLeft size={13} /> Contribute</button>
                        <button onClick={() => { setMove({ member: m, kind: "payout" }); setMoveForm({ amount: "", cash_account_id: "" }); }} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-100"><ArrowUpRight size={13} /> Payout</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={4} className="py-16 text-center text-slate-400"><Handshake size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No members yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
