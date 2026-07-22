"use client";

import { useMemo, useState } from "react";
import {
  useParentWallets, useParentWallet, useParentWalletSummary, useInitializeParentWallets,
  useAddParentCredit, useParentWalletSettings, useUpdateParentWalletSettings,
} from "@/hooks/useWallet";
import { useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { walletApi } from "@/lib/api";
import { cn, formatCurrency } from "@/lib/utils";
import {
  Wallet, Users, ArrowDownLeft, ArrowUpRight, PiggyBank, Loader2, AlertTriangle, X,
  FileText, RefreshCw, Trash2, FileSpreadsheet, Power, Download, Settings2, Save, Lock,
  ChevronLeft, Plus, Info,
} from "lucide-react";
import type { ParentWallet } from "@/types";

const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—");

function downloadBlob(data: BlobPart, filename: string, type = "text/csv") {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

/** A toolbar icon; gateway-dependent ones render disabled with an explanatory title. */
function ToolBtn({ icon: Icon, title, tint, onClick, disabled, busy }: { icon: any; title: string; tint: string; onClick?: () => void; disabled?: boolean; busy?: boolean }) {
  return (
    <button type="button" title={title} onClick={onClick} disabled={disabled || busy}
      className={cn("w-11 h-11 rounded-lg flex items-center justify-center text-white transition-opacity", tint, (disabled || busy) && "opacity-40 cursor-not-allowed")}>
      {busy ? <Loader2 size={18} className="animate-spin" /> : <Icon size={18} />}
    </button>
  );
}

export default function WalletManagerPage() {
  const canPost = useHasPermission("payments:post");
  const canWrite = useHasPermission("payments:write");

  const { data: summary } = useParentWalletSummary();
  const { data, isLoading, isError, refetch } = useParentWallets();
  const init = useInitializeParentWallets();

  const [tab, setTab] = useState<"list" | "settings">("list");
  const [detailId, setDetailId] = useState<string | null>(null);

  const rows: ParentWallet[] = data?.items ?? [];

  const exportList = () => {
    const header = ["Parent", "Email", "Phone", "Credits", "Debits", "Balance", "Children"];
    const lines = rows.map((w) => [w.parent_name ?? "", w.parent_email ?? "", w.parent_phone ?? "",
      w.credit_total, w.debit_total, w.balance, w.children.map((c) => c.name).join("; ")]);
    const csv = [header, ...lines].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    downloadBlob(csv, "wallet-ledger.csv");
  };

  if (detailId) return <LedgerView walletId={detailId} onBack={() => setDetailId(null)} />;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Home</span><span>/</span><span className="text-brand-600 font-semibold">Wallet Manager</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Wallet Manager</h1>
        <p className="text-slate-500 text-sm mt-0.5">Parent (family) wallets — funded by parents to pay their children’s invoices. Balances are ledger-derived.</p>
      </div>

      {/* Dashboard cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="rounded-2xl p-5 bg-emerald-500 text-white flex items-center justify-between">
          <ArrowDownLeft size={44} className="opacity-30" />
          <div className="text-right">
            <p className="text-2xl font-black">{formatCurrency(summary?.total_credits ?? 0)}</p>
            <p className="text-xs font-semibold opacity-90">Total Credits</p>
            <p className="text-lg font-black mt-1">{formatCurrency(summary?.today_credits ?? 0)}</p>
            <p className="text-[11px] opacity-80">Today’s Credits</p>
          </div>
        </div>
        <div className="rounded-2xl p-5 bg-rose-500 text-white flex items-center justify-between">
          <ArrowUpRight size={44} className="opacity-30" />
          <div className="text-right">
            <p className="text-2xl font-black">{formatCurrency(summary?.total_debits ?? 0)}</p>
            <p className="text-xs font-semibold opacity-90">Total Debits</p>
            <p className="text-lg font-black mt-1">{formatCurrency(summary?.today_debits ?? 0)}</p>
            <p className="text-[11px] opacity-80">Today’s Debits</p>
          </div>
        </div>
        <div className="rounded-2xl p-5 bg-sky-500 text-white flex items-center justify-between">
          <PiggyBank size={44} className="opacity-30" />
          <div className="text-right">
            <p className="text-2xl font-black">{formatCurrency(summary?.cumulative_balance ?? 0)}</p>
            <p className="text-xs font-semibold opacity-90">Cumulative Wallet Balance</p>
            <p className="text-lg font-black mt-1">{summary?.total_active_wallets ?? 0}</p>
            <p className="text-[11px] opacity-80">Total Active Wallets</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-200 mb-5">
        {([["list", "Wallet List"], ["settings", "Wallet Settings"]] as const).map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2.5 text-sm font-bold border-b-2 -mb-px transition-colors uppercase tracking-wide",
            tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-400 hover:text-slate-600")}>{label}</button>
        ))}
      </div>

      {tab === "list" ? (
        <>
          {/* Toolbar */}
          <div className="bg-brand-700 rounded-t-xl px-4 py-3 flex items-center justify-between">
            <p className="text-white font-bold text-sm flex items-center gap-2"><Wallet size={16} /> Manage Wallet Information</p>
            <div className="flex items-center gap-2">
              {canWrite && <ToolBtn icon={Users} title="Initialize Wallet for all new Parents" tint="bg-sky-400 hover:bg-sky-500" onClick={() => init.mutate()} busy={init.isPending} />}
              <ToolBtn icon={RefreshCw} title="Bulk Requery — requires Payment Gateway" tint="bg-amber-400" disabled />
              <ToolBtn icon={RefreshCw} title="Sync residual invoices — requires Payment Gateway" tint="bg-rose-400" disabled />
              <ToolBtn icon={Trash2} title="Run wallet DVA delete command — requires Payment Gateway" tint="bg-rose-500" disabled />
              <ToolBtn icon={FileSpreadsheet} title="Download Wallet Ledger" tint="bg-emerald-500 hover:bg-emerald-600" onClick={exportList} disabled={rows.length === 0} />
            </div>
          </div>

          <div className="bg-white rounded-b-xl border border-slate-200 border-t-0 overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Wallet Profile", "Transaction History (₦)", "Status", "Account Number", "Children", "Actions"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-slate-50">
                {isLoading ? (
                  Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 7 }).map((_, j) => <td key={j} className="px-4 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-16" /></td>)}</tr>)
                ) : isError ? (
                  <tr><td colSpan={7} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load wallets.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
                ) : rows.length > 0 ? (
                  rows.map((w, i) => (
                    <tr key={w.id} className="hover:bg-slate-50/70 align-top">
                      <td className="px-4 py-4 text-sm text-slate-500">{i + 1}</td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <p className="text-sm font-bold text-slate-800 uppercase">{w.parent_name || "—"}</p>
                        <p className="text-xs text-slate-400">{w.parent_email || ""}</p>
                        <p className="text-xs text-slate-400">{w.parent_phone || ""}</p>
                      </td>
                      <td className="px-4 py-4 text-xs whitespace-nowrap">
                        <p className="text-emerald-600">Credit: <span className="font-bold">{formatCurrency(w.credit_total)}</span></p>
                        <p className="text-rose-600">Debit: <span className="font-bold">{formatCurrency(w.debit_total)}</span></p>
                        <p className="text-slate-800">Balance: <span className="font-bold">{formatCurrency(w.balance)}</span></p>
                      </td>
                      <td className="px-4 py-4"><span className={cn("badge", w.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{w.is_active ? "ACTIVE" : "INACTIVE"}</span></td>
                      <td className="px-4 py-4"><span title="Virtual account — requires Payment Gateway" className="inline-flex items-center gap-1 text-slate-300"><Power size={16} /></span></td>
                      <td className="px-4 py-4 text-sm">
                        {w.children.length === 0 ? <span className="text-slate-300">—</span> : (
                          <div className="space-y-0.5">{w.children.map((c) => <p key={c.id} className="text-brand-600 whitespace-nowrap">{c.name} {c.class_name && <span className="text-slate-400">({c.class_name})</span>}</p>)}</div>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex flex-col gap-1.5 items-stretch">
                          <button onClick={() => setDetailId(w.id)} className="inline-flex items-center justify-center gap-1 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 px-2.5 py-1.5 rounded"><FileText size={13} /> Details</button>
                          {canPost && <AddCreditButton wallet={w} />}
                          <button title="Requery — requires Payment Gateway" disabled className="inline-flex items-center justify-center gap-1 text-xs font-semibold text-white bg-amber-400 px-2.5 py-1.5 rounded opacity-40 cursor-not-allowed"><RefreshCw size={13} /> Requery</button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan={7} className="py-16 text-center text-slate-400"><Wallet size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No parent wallets yet</p>{canWrite && <p className="text-xs mt-1">Use “Initialize Wallet for all new Parents” above to create them.</p>}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <WalletSettingsTab canWrite={canWrite} />
      )}
    </div>
  );
}

/** Add Credit — inline modal trigger. */
function AddCreditButton({ wallet }: { wallet: ParentWallet }) {
  const { data: accounts } = useAccounts({ active_only: true });
  const credit = useAddParentCredit();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ amount: "", cash_account_id: "", memo: "" });
  const cashAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset"), [accounts]);
  const close = () => { setOpen(false); setForm({ amount: "", cash_account_id: "", memo: "" }); };
  const submit = () => credit.mutate({ id: wallet.id, data: { amount: Number(form.amount), cash_account_id: form.cash_account_id, memo: form.memo || null } }, { onSuccess: close });

  return (
    <>
      <button onClick={() => setOpen(true)} className="inline-flex items-center justify-center gap-1 text-xs font-semibold text-white bg-teal-500 hover:bg-teal-600 px-2.5 py-1.5 rounded"><Plus size={13} /> Add Credit</button>
      {open && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={close}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md text-left" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Add Credit — {wallet.parent_name}</h3><button onClick={close} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 space-y-4">
              <div><label className="label">Amount *</label><input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="input" /></div>
              <div><label className="label">Funded into cash account *</label><select value={form.cash_account_id} onChange={(e) => setForm({ ...form, cash_account_id: e.target.value })} className="input"><option value="">Select…</option>{cashAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
              <div><label className="label">Memo</label><input value={form.memo} onChange={(e) => setForm({ ...form, memo: e.target.value })} className="input" placeholder="optional" /></div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={close} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.amount || !form.cash_account_id || credit.isPending} className="btn-primary gap-2">{credit.isPending && <Loader2 size={15} className="animate-spin" />}Add Credit</button></div>
          </div>
        </div>
      )}
    </>
  );
}

/** WALLET SETTINGS tab — only the non-gateway settings; DVA config is deferred. */
function WalletSettingsTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = useParentWalletSettings();
  const update = useUpdateParentWalletSettings();
  const [f, setF] = useState<{ auto_invoice_pay: boolean; correspondent_email: string } | null>(null);
  const state = f ?? { auto_invoice_pay: data?.auto_invoice_pay ?? false, correspondent_email: data?.correspondent_email ?? "" };
  const save = () => update.mutate({ auto_invoice_pay: state.auto_invoice_pay, correspondent_email: state.correspondent_email || null });

  if (isLoading) return <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}</div>;

  return (
    <div className="bg-white rounded-xl border border-slate-200 max-w-2xl">
      <div className="px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Wallet Settings</h3></div>
      <div className="divide-y divide-slate-100">
        <div className="px-6 py-5 flex items-center justify-between gap-4">
          <div><p className="text-sm font-semibold text-slate-800">Enable Automatic Invoice Pay with Wallet Balance</p><p className="text-xs text-slate-400">Settle a child’s invoice automatically from the parent’s wallet balance.</p></div>
          <button type="button" disabled={!canWrite} onClick={() => setF({ ...state, auto_invoice_pay: !state.auto_invoice_pay })}
            className={cn("relative inline-flex h-6 w-11 items-center rounded-full transition-colors shrink-0", state.auto_invoice_pay ? "bg-brand-600" : "bg-slate-300", !canWrite && "opacity-50")}>
            <span className={cn("inline-block h-4 w-4 transform rounded-full bg-white transition-transform", state.auto_invoice_pay ? "translate-x-6" : "translate-x-1")} />
          </button>
        </div>
        <div className="px-6 py-5">
          <label className="label">Wallet Correspondent email Address</label>
          <input value={state.correspondent_email} onChange={(e) => setF({ ...state, correspondent_email: e.target.value })} disabled={!canWrite} className="input" placeholder="Email to receive wallet credit notifications" />
        </div>
        <div className="px-6 py-4 bg-slate-50/60 flex items-start gap-2 text-xs text-slate-500">
          <Info size={14} className="mt-0.5 shrink-0 text-slate-400" />
          <span>Virtual account settings (Wallet Account Number, Default BVN, Virtual Account Gateway, Preferred DVA Bank) require the Payment Gateway integration and will appear here once it’s enabled.</span>
        </div>
      </div>
      {canWrite && <div className="px-6 py-4 border-t border-slate-100 flex justify-end"><button onClick={save} disabled={update.isPending} className="btn-primary gap-2">{update.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save Change</button></div>}
      {!canWrite && <div className="px-6 py-4 border-t border-slate-100 text-xs text-slate-400 flex items-center gap-1"><Lock size={12} /> Editing requires payments write access.</div>}
    </div>
  );
}

/** Details → Wallet Ledger view: WALLET LEDGER / CREDIT LIST / DEBIT LIST. */
function LedgerView({ walletId, onBack }: { walletId: string; onBack: () => void }) {
  const { data: w, isLoading } = useParentWallet(walletId);
  const [lt, setLt] = useState<"ledger" | "credit" | "debit">("ledger");
  const [busy, setBusy] = useState(false);

  const download = async () => {
    setBusy(true);
    try { downloadBlob(await walletApi.parent.ledgerCsv(walletId), `wallet-ledger-${walletId}.csv`); }
    finally { setBusy(false); }
  };

  const entries = w?.entries ?? [];
  const shown = lt === "credit" ? entries.filter((e) => e.kind === "credit") : lt === "debit" ? entries.filter((e) => e.kind === "debit") : entries;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center gap-1 border-b border-slate-200 mb-5">
        {([["ledger", "Wallet Ledger"], ["credit", "Credit List"], ["debit", "Debit List"]] as const).map(([k, label]) => (
          <button key={k} onClick={() => setLt(k)} className={cn("px-4 py-2.5 text-sm font-bold border-b-2 -mb-px uppercase tracking-wide",
            lt === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-400 hover:text-slate-600")}>{label}</button>
        ))}
        <button onClick={onBack} className="ml-auto inline-flex items-center gap-1 text-sm font-semibold text-slate-500 hover:text-slate-700 px-3 py-2"><ChevronLeft size={15} /> Back to List</button>
      </div>

      {isLoading || !w ? (
        <div className="space-y-3">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : (
        <>
          <div className="bg-brand-700 rounded-t-xl px-5 py-3 flex items-center justify-between">
            <p className="text-white font-bold text-sm flex items-center gap-2"><Wallet size={16} /> Wallet Ledger For {w.parent_name}</p>
            <button onClick={download} disabled={busy} className="inline-flex items-center gap-1.5 text-sm font-semibold text-white bg-emerald-500 hover:bg-emerald-600 px-3 py-1.5 rounded">{busy ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />} Download</button>
          </div>
          <div className="bg-white rounded-b-xl border border-slate-200 border-t-0 p-6">
            {lt === "ledger" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6 pb-6 border-b border-slate-100">
                <div>
                  <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">Wallet Account Summary</p>
                  <p className="text-sm text-slate-600">Wallet Credits <span className="font-bold text-emerald-600">{formatCurrency(w.credit_total)}</span></p>
                  <p className="text-sm text-slate-600">Wallet Debits <span className="font-bold text-rose-600">{formatCurrency(w.debit_total)}</span></p>
                  <p className="text-sm text-slate-600">Wallet Current Balance <span className="font-bold text-slate-900">{formatCurrency(w.balance)}</span></p>
                </div>
                <div className="rounded-lg bg-emerald-50 border border-emerald-100 p-4 text-sm">
                  <p className="font-bold text-emerald-700">No Discrepancy</p>
                  <p className="text-emerald-600 text-xs mt-0.5">Debit/Credit log for this wallet is as expected.</p>
                </div>
              </div>
            )}
            <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Wallet Transaction Entries</p>
            {shown.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-10">No {lt === "ledger" ? "" : lt + " "}entries.</p>
            ) : (
              <div className="divide-y divide-slate-50">
                {shown.map((e) => (
                  <div key={e.id} className={cn("flex items-center gap-3 py-3", e.reversed && "opacity-50")}>
                    <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center shrink-0", e.signed_amount >= 0 ? "bg-emerald-50 text-emerald-600" : "bg-rose-50 text-rose-600")}>{e.signed_amount >= 0 ? <ArrowDownLeft size={14} /> : <ArrowUpRight size={14} />}</div>
                    <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-700 capitalize">{e.kind}{e.reversed && <span className="ml-2 text-[10px] font-bold text-rose-500">reversed</span>}</p><p className="text-xs text-slate-400 truncate">{fmtDate(e.created_at)}{e.memo ? ` · ${e.memo}` : ""}</p></div>
                    <span className={cn("text-sm font-bold whitespace-nowrap", e.signed_amount >= 0 ? "text-emerald-600" : "text-rose-600")}>{e.signed_amount >= 0 ? "+" : ""}{formatCurrency(e.signed_amount)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
