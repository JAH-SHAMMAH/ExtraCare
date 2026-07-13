"use client";

import { useMemo, useState } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import {
  useCoopMembers, useCreateMember, useContribute, usePayout, useCoopReconciliation,
} from "@/hooks/useWallet";
import { useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Handshake, Plus, X, Loader2, AlertTriangle, Scale, ArrowDownLeft, ArrowUpRight, Users2, Wallet, Printer } from "lucide-react";
import { PrintLetterhead } from "@/components/branding/Brand";
import type { CooperativeMember } from "@/types";

type Tab = "console" | "dashboard" | "reports";
const TABS: Tab[] = ["console", "dashboard", "reports"];

export default function CooperativePage() {
  // Tab lives in the URL (?tab=…) so the sidebar's Cooperative sub-items deep-link.
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const raw = searchParams.get("tab");
  const tab: Tab = TABS.includes(raw as Tab) ? (raw as Tab) : "console";
  const setTab = (t: Tab) => router.replace(`${pathname}?tab=${t}`, { scroll: false });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-5">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Cooperative</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Cooperative</h1>
        <p className="text-slate-500 text-sm mt-0.5">Member savings held on their behalf (a liability) — contributions &amp; payouts, ledger-backed.</p>
      </div>
      <div className="flex gap-1 border-b border-slate-200 mb-6 no-print">
        {([["console", "Console"], ["dashboard", "Dashboard"], ["reports", "Reports"]] as [Tab, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>
      {tab === "console" ? <Console /> : tab === "dashboard" ? <CoopDashboard /> : <CoopReports />}
    </div>
  );
}

// ── Console — member management (contributions / payouts) ─────────────────────────

function Console() {
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
    <>
      <div className="flex justify-end mb-4">
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

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
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
    </>
  );
}

// ── Dashboard — at-a-glance summary ───────────────────────────────────────────────

function CoopDashboard() {
  const { data } = useCoopMembers();
  const { data: recon } = useCoopReconciliation();
  const members = data?.items ?? [];
  const active = members.filter((m) => m.is_active).length;
  const fund = members.reduce((sum, m) => sum + (m.balance || 0), 0);

  const cards = [
    { label: "Members", value: members.length.toLocaleString(), icon: Users2, tint: "bg-brand-50 text-brand-600" },
    { label: "Active", value: active.toLocaleString(), icon: Handshake, tint: "bg-emerald-50 text-emerald-600" },
    { label: "Fund held", value: fund.toFixed(2), icon: Wallet, tint: "bg-indigo-50 text-indigo-600" },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
            <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center mb-3", c.tint)}><c.icon size={16} /></div>
            <p className="text-2xl font-black tracking-tight tabular-nums text-slate-900">{c.value}</p>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mt-1">{c.label}</p>
          </div>
        ))}
      </div>
      {recon && (
        <div className={cn("flex items-center gap-2 text-sm rounded-xl px-4 py-3 border", recon.balanced ? "text-emerald-700 bg-emerald-50 border-emerald-200" : "text-rose-700 bg-rose-50 border-rose-200")}>
          <Scale size={16} />
          <span><strong>Reconciliation:</strong> general-ledger fund {recon.gl_balance.toFixed(2)} vs. member balances {recon.subledger_total.toFixed(2)} — {recon.balanced ? "balanced ✓" : "OUT OF BALANCE — investigate"}</span>
        </div>
      )}
    </div>
  );
}

// ── Reports — printable member balance statement ─────────────────────────────────

function CoopReports() {
  const { data, isLoading } = useCoopMembers();
  const members = data?.items ?? [];
  const total = members.reduce((sum, m) => sum + (m.balance || 0), 0);

  return (
    <div>
      <div className="flex justify-end mb-4 no-print">
        <button onClick={() => window.print()} className="btn-secondary gap-2"><Printer size={14} /> Print statement</button>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-6 print:border-0 print:p-0">
        <PrintLetterhead title="Cooperative — Member Balances" />
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : members.length === 0 ? (
          <p className="py-12 text-center text-slate-400 text-sm">No members yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Member", "Status", "Balance"].map((h) => <th key={h} className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-slate-50">
                {members.map((m, i) => (
                  <tr key={m.id}>
                    <td className="px-4 py-2.5 text-xs text-slate-400 tabular-nums">{i + 1}</td>
                    <td className="px-4 py-2.5 text-sm font-medium text-slate-800">{m.member_name}</td>
                    <td className="px-4 py-2.5 text-xs capitalize text-slate-500">{m.is_active ? "active" : "inactive"}</td>
                    <td className="px-4 py-2.5 text-sm font-semibold text-slate-900 tabular-nums">{m.balance.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr className="border-t-2 border-slate-200"><td /><td /><td className="px-4 py-2.5 text-xs font-bold uppercase text-slate-500 text-right">Total fund</td><td className="px-4 py-2.5 text-sm font-black text-slate-900 tabular-nums">{total.toFixed(2)}</td></tr></tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
