"use client";

import Link from "next/link";
import { useWalletSummary, useWalletReconciliation } from "@/hooks/useWallet";
import { formatCurrency, cn } from "@/lib/utils";
import {
  Wallet, Users, CheckCircle2, ArrowDownLeft, ArrowUpRight, PiggyBank,
  Scale, Settings2, ListChecks, AlertTriangle, Loader2,
} from "lucide-react";

function Card({ icon: Icon, label, value, tint }: { icon: any; label: string; value: string; tint: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-center gap-3">
        <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center shrink-0", tint)}><Icon size={18} /></div>
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
          <p className="text-xl font-black text-slate-900 truncate">{value}</p>
        </div>
      </div>
    </div>
  );
}

export default function WalletDashboardPage() {
  const { data: s, isLoading, isError, refetch } = useWalletSummary();
  const { data: recon } = useWalletReconciliation();

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Wallet Manager</span><span>/</span><span className="text-brand-600 font-semibold">Dashboard</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Wallet Manager</h1>
        <p className="text-slate-500 text-sm mt-0.5">Cashless student wallets funded by parents — balances are ledger-derived and reconcile to the GL.</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError || !s ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load the wallet summary.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <Card icon={Wallet} label="Total Wallets" value={String(s.total_wallets)} tint="bg-brand-50 text-brand-600" />
            <Card icon={CheckCircle2} label="Active Wallets" value={String(s.active_wallets)} tint="bg-emerald-50 text-emerald-600" />
            <Card icon={Users} label="Inactive" value={String(s.inactive_wallets)} tint="bg-slate-100 text-slate-500" />
            <Card icon={PiggyBank} label="Total Balance" value={formatCurrency(s.total_balance)} tint="bg-indigo-50 text-indigo-600" />
            <Card icon={ArrowDownLeft} label="Total Credited" value={formatCurrency(s.total_topped_up)} tint="bg-emerald-50 text-emerald-600" />
            <Card icon={ArrowUpRight} label="Total Spent" value={formatCurrency(s.total_spent)} tint="bg-rose-50 text-rose-600" />
          </div>

          {recon && (
            <div className={cn("flex items-center gap-2 text-xs rounded-lg px-3 py-2.5 mt-5 border", recon.balanced ? "text-emerald-700 bg-emerald-50 border-emerald-200" : "text-rose-700 bg-rose-50 border-rose-200")}>
              <Scale size={14} className="shrink-0" />
              Reconciliation — GL float {formatCurrency(recon.gl_balance)} vs wallet balances {formatCurrency(recon.subledger_total)}: {recon.balanced ? "balanced ✓" : "OUT OF BALANCE"}
            </div>
          )}

          <div className="flex flex-wrap gap-3 mt-6">
            <Link href="/dashboard/modules/school/wallet/list" className="btn-primary gap-2"><ListChecks size={15} /> Open Wallet List</Link>
            <Link href="/dashboard/modules/school/wallet/settings" className="btn-secondary gap-2"><Settings2 size={15} /> Wallet Settings</Link>
          </div>
        </>
      )}
    </div>
  );
}
