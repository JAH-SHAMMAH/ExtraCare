"use client";

import { useEffect, useState } from "react";
import { useWalletSettings, useUpdateWalletSettings } from "@/hooks/useWallet";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Settings2, Loader2, AlertTriangle, Lock, Save } from "lucide-react";

function Toggle({ on, onChange, disabled }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button type="button" disabled={disabled} onClick={() => onChange(!on)}
      className={cn("relative inline-flex h-6 w-11 items-center rounded-full transition-colors shrink-0", on ? "bg-brand-600" : "bg-slate-300", disabled && "opacity-50 cursor-not-allowed")}>
      <span className={cn("inline-block h-4 w-4 transform rounded-full bg-white transition-transform", on ? "translate-x-6" : "translate-x-1")} />
    </button>
  );
}

export default function WalletSettingsPage() {
  const canWrite = useHasPermission("payments:write");
  const { data, isLoading, isError, refetch } = useWalletSettings();
  const update = useUpdateWalletSettings();

  const [f, setF] = useState({ default_daily_limit: "", low_balance_threshold: "", notify_low_balance: false, allow_topup: true });

  useEffect(() => {
    if (data) setF({
      default_daily_limit: data.default_daily_limit != null ? String(data.default_daily_limit) : "",
      low_balance_threshold: data.low_balance_threshold != null ? String(data.low_balance_threshold) : "",
      notify_low_balance: data.notify_low_balance,
      allow_topup: data.allow_topup,
    });
  }, [data]);

  const save = () => update.mutate({
    default_daily_limit: f.default_daily_limit === "" ? null : Number(f.default_daily_limit),
    low_balance_threshold: f.low_balance_threshold === "" ? null : Number(f.low_balance_threshold),
    notify_low_balance: f.notify_low_balance,
    allow_topup: f.allow_topup,
  });

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Wallet Manager</span><span>/</span><span className="text-brand-600 font-semibold">Wallet Settings</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Wallet Settings</h1>
        <p className="text-slate-500 text-sm mt-0.5">Org-wide defaults for the wallet system — applied to new wallets and the low-balance flag.</p>
      </div>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load wallet settings.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <label className="label">Default daily spend limit</label>
              <input type="number" value={f.default_daily_limit} onChange={(e) => setF({ ...f, default_daily_limit: e.target.value })} disabled={!canWrite} className="input" placeholder="blank = unlimited" />
              <p className="text-xs text-slate-400 mt-1">Applied to a new wallet when no limit is set on creation.</p>
            </div>
            <div>
              <label className="label">Low-balance threshold</label>
              <input type="number" value={f.low_balance_threshold} onChange={(e) => setF({ ...f, low_balance_threshold: e.target.value })} disabled={!canWrite} className="input" placeholder="blank = no flag" />
              <p className="text-xs text-slate-400 mt-1">Wallets below this are flagged as running low.</p>
            </div>
          </div>

          <div className="p-6 flex items-center justify-between gap-4">
            <div><p className="text-sm font-semibold text-slate-800">Notify on low balance</p><p className="text-xs text-slate-400">Alert when a wallet falls below the threshold.</p></div>
            <Toggle on={f.notify_low_balance} onChange={(v) => setF({ ...f, notify_low_balance: v })} disabled={!canWrite} />
          </div>

          <div className="p-6 flex items-center justify-between gap-4">
            <div><p className="text-sm font-semibold text-slate-800">Allow top-ups (Add Credit)</p><p className="text-xs text-slate-400">Turn off to temporarily freeze all wallet funding.</p></div>
            <Toggle on={f.allow_topup} onChange={(v) => setF({ ...f, allow_topup: v })} disabled={!canWrite} />
          </div>

          <div className="p-6 flex items-center justify-between">
            {!canWrite ? (
              <p className="text-xs text-slate-400 flex items-center gap-1"><Lock size={12} /> Editing requires payments write access.</p>
            ) : <span />}
            {canWrite && <button onClick={save} disabled={update.isPending} className="btn-primary gap-2">{update.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save settings</button>}
          </div>
        </div>
      )}
    </div>
  );
}
