"use client";

import { useMemo, useState } from "react";
import { useBroadViewDashboard, useAccountHeadSummary, useTermlySummary, useDiscountLog, useWalletLog } from "@/hooks/useFinance";
import { useSessions } from "@/hooks/usePlatform";
import { cn, formatCurrency } from "@/lib/utils";
import {
  Receipt, CheckCircle2, Layers, Landmark, TrendingUp, ArrowDownLeft, ArrowUpRight,
  AlertOctagon, Loader2, AlertTriangle, BarChart3, Building2,
} from "lucide-react";

const fmtDate = (d?: string) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—");

function TabTable({ headers, children }: { headers: string[]; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
      <table className="w-full text-left">
        <thead><tr className="bg-slate-50/80 border-b border-slate-100">{headers.map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-50">{children}</tbody>
      </table>
    </div>
  );
}

function AccountHeadTab() {
  const { data, isLoading } = useAccountHeadSummary(true);
  const rows = data?.items ?? [];
  return (
    <TabTable headers={["SN", "Account Name", "Total Invoice", "Total Receipt", "Invoice Charge", "Amount Paid"]}>
      {isLoading ? <tr><td colSpan={6} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
      : rows.length ? rows.map((r: any, i: number) => (
        <tr key={r.account_name} className="hover:bg-slate-50/70">
          <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
          <td className="px-5 py-3 text-sm font-semibold text-slate-800">{r.account_name}</td>
          <td className="px-5 py-3 text-sm text-slate-600">{r.total_invoice}</td>
          <td className="px-5 py-3 text-sm text-slate-600">{r.total_receipt}</td>
          <td className="px-5 py-3 text-sm font-semibold text-slate-800">{formatCurrency(r.invoice_charge)}</td>
          <td className="px-5 py-3 text-sm font-semibold text-emerald-600">{formatCurrency(r.amount_paid)}</td>
        </tr>
      )) : <tr><td colSpan={6} className="py-14 text-center text-slate-400 font-semibold">No data available</td></tr>}
    </TabTable>
  );
}

function TermlyTab({ session, term }: { session: string; term: string }) {
  const { data, isLoading } = useTermlySummary({ session: session || undefined, term: term || undefined }, true);
  const rows = data?.items ?? [];
  return (
    <>
      <TabTable headers={["SN", "Fee Category", "Amount"]}>
        {isLoading ? <tr><td colSpan={3} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
        : rows.map((r: any, i: number) => (
          <tr key={r.fee} className="hover:bg-slate-50/70">
            <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
            <td className="px-5 py-3 text-sm font-semibold text-slate-800">{r.fee}</td>
            <td className="px-5 py-3 text-sm text-slate-700">{formatCurrency(r.amount)}</td>
          </tr>
        ))}
      </TabTable>
      {data && <p className="text-right text-sm font-bold text-slate-800 mt-3">Total: {formatCurrency(data.total)}</p>}
    </>
  );
}

function DiscountTab() {
  const { data, isLoading } = useDiscountLog(true);
  const rows = data?.items ?? [];
  return (
    <>
      {data && <div className="mb-4"><span className="inline-block bg-rose-50 text-rose-700 border border-rose-100 rounded-lg px-4 py-2 text-sm font-bold">Total Discount (approved): {formatCurrency(data.total_discount)}</span></div>}
      <TabTable headers={["SN", "Student", "Type", "Value", "Discount Given", "Reason", "Status", "Date"]}>
        {isLoading ? <tr><td colSpan={8} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
        : rows.length ? rows.map((r: any, i: number) => (
          <tr key={r.id} className="hover:bg-slate-50/70">
            <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
            <td className="px-5 py-3 text-sm font-semibold text-slate-800">{r.student_name || "—"}</td>
            <td className="px-5 py-3 text-sm text-slate-600 capitalize">{r.discount_type}</td>
            <td className="px-5 py-3 text-sm text-slate-600">{r.discount_type === "percent" ? `${r.value}%` : formatCurrency(r.value)}</td>
            <td className="px-5 py-3 text-sm font-semibold text-rose-600">{formatCurrency(r.amount)}</td>
            <td className="px-5 py-3 text-sm text-slate-600">{r.reason || "—"}</td>
            <td className="px-5 py-3"><span className={cn("badge capitalize", r.status === "approved" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-500 border-slate-200")}>{r.status}</span></td>
            <td className="px-5 py-3 text-sm text-slate-500 whitespace-nowrap">{fmtDate(r.created_at)}</td>
          </tr>
        )) : <tr><td colSpan={8} className="py-14 text-center text-slate-400 font-semibold">No discounts</td></tr>}
      </TabTable>
    </>
  );
}

function WalletTab() {
  const { data, isLoading } = useWalletLog(true);
  const rows = data?.items ?? [];
  return (
    <>
      {data && (
        <div className="grid grid-cols-2 gap-4 mb-4 max-w-md">
          <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-4"><p className="text-lg font-black text-emerald-700">{formatCurrency(data.total_credit)}</p><p className="text-[11px] font-bold uppercase tracking-widest text-emerald-500">Total Credit</p></div>
          <div className="rounded-xl border border-rose-100 bg-rose-50 p-4"><p className="text-lg font-black text-rose-700">{formatCurrency(data.total_debit)}</p><p className="text-[11px] font-bold uppercase tracking-widest text-rose-500">Total Debit</p></div>
        </div>
      )}
      <TabTable headers={["SN", "Wallet Name", "Description", "Credit", "Debit", "Date"]}>
        {isLoading ? <tr><td colSpan={6} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
        : rows.length ? rows.map((r: any, i: number) => (
          <tr key={r.id} className="hover:bg-slate-50/70">
            <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
            <td className="px-5 py-3 text-sm font-semibold text-slate-800">{r.wallet_name || "—"}</td>
            <td className="px-5 py-3 text-sm text-slate-500">{r.memo || "—"}</td>
            <td className="px-5 py-3 text-sm font-semibold text-emerald-600">{r.credit ? formatCurrency(r.credit) : "—"}</td>
            <td className="px-5 py-3 text-sm font-semibold text-rose-600">{r.debit ? formatCurrency(r.debit) : "—"}</td>
            <td className="px-5 py-3 text-sm text-slate-500 whitespace-nowrap">{fmtDate(r.created_at)}</td>
          </tr>
        )) : <tr><td colSpan={6} className="py-14 text-center text-slate-400 font-semibold">No wallet transactions</td></tr>}
      </TabTable>
    </>
  );
}

const TABS = [
  "Report Dashboard", "Invoice Items Report", "Students Ledger", "All Transactions Log",
  "Payment Refs", "Audit Report", "Online Transactions Log", "Account Head Summary",
  "Termly Summary", "Discount Log", "Wallet Log", "Admission Form Pay Log",
];

function Card({ icon: Icon, label, value, tint }: { icon: any; label: string; value: string; tint: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center justify-between">
      <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center shrink-0", tint)}><Icon size={20} /></div>
      <div className="text-right min-w-0">
        <p className="text-xl font-black text-slate-900 truncate">{value}</p>
        <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
      </div>
    </div>
  );
}

export default function BroadViewPage() {
  const { data: sessions } = useSessions();
  const sessionNames = useMemo(() => Array.from(new Set((sessions ?? []).map((s: any) => s.name))), [sessions]);
  const [session, setSession] = useState("");
  const [term, setTerm] = useState("");
  const termsFor = useMemo(() => Array.from(new Set((sessions ?? []).filter((s: any) => s.name === session).map((s: any) => s.term).filter(Boolean))), [sessions, session]);
  const [tab, setTab] = useState("Report Dashboard");

  const { data, isLoading, isError, refetch } = useBroadViewDashboard({ session: session || undefined, term: term || undefined });
  const d: any = data;
  const maxDist = Math.max(1, ...((d?.distribution ?? []).map((x: any) => Math.abs(x.amount))));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Broad View</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">Broad View <span className="text-[9px] font-bold uppercase bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">beta</span></h1>
        <p className="text-slate-500 text-sm mt-0.5">Consolidated finance reporting — invoices, payments, revenue distribution and live bank balances.</p>
      </div>

      {/* Session / Term */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5 flex flex-wrap gap-4 items-end max-w-lg">
        <div className="flex-1 min-w-[140px]"><label className="label">Select Session</label><select value={session} onChange={(e) => { setSession(e.target.value); setTerm(""); }} className="input"><option value="">All Sessions</option>{sessionNames.map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div className="flex-1 min-w-[140px]"><label className="label">Term</label><select value={term} onChange={(e) => setTerm(e.target.value)} className="input"><option value="">All Terms</option>{termsFor.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-x-4 gap-y-1 border-b border-slate-200 mb-6 flex-wrap">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={cn("py-2.5 text-xs font-bold uppercase tracking-wide border-b-2 -mb-px whitespace-nowrap", tab === t ? "border-brand-600 text-brand-700" : "border-transparent text-slate-400 hover:text-slate-600")}>{t}</button>
        ))}
      </div>

      {tab === "Account Head Summary" ? (
        <AccountHeadTab />
      ) : tab === "Termly Summary" ? (
        <TermlyTab session={session} term={term} />
      ) : tab === "Discount Log" ? (
        <DiscountTab />
      ) : tab === "Wallet Log" ? (
        <WalletTab />
      ) : tab !== "Report Dashboard" ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <BarChart3 size={30} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-slate-500">{tab}</p>
          <p className="text-xs mt-1">This report is coming in the next update.</p>
        </div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load the dashboard.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : isLoading || !d ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : (
        <>
          {/* Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            <Card icon={Receipt} label="Invoices" value={String(d.invoices)} tint="bg-indigo-50 text-indigo-600" />
            <Card icon={CheckCircle2} label="Full Payments" value={String(d.full_payments)} tint="bg-emerald-50 text-emerald-600" />
            <Card icon={Layers} label="Part Payments" value={String(d.part_payments)} tint="bg-amber-50 text-amber-600" />
            <Card icon={Landmark} label="Bank Accounts" value={String(d.bank_accounts)} tint="bg-sky-50 text-sky-600" />
            <Card icon={TrendingUp} label="Total Revenue" value={formatCurrency(d.total_revenue)} tint="bg-yellow-50 text-yellow-600" />
            <Card icon={ArrowDownLeft} label="Total Full Payment" value={formatCurrency(d.total_full_payment)} tint="bg-emerald-50 text-emerald-600" />
            <Card icon={ArrowUpRight} label="Total Part Payment" value={formatCurrency(d.total_part_payment)} tint="bg-teal-50 text-teal-600" />
            <Card icon={AlertOctagon} label="Total Debt" value={formatCurrency(d.total_debt)} tint="bg-rose-50 text-rose-600" />
          </div>

          {/* Transaction Distribution */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 mb-4">
            <h3 className="text-sm font-black uppercase tracking-widest text-slate-400 mb-4 flex items-center gap-2"><BarChart3 size={15} /> Transaction Distribution {session && <span className="text-slate-300">· {session}</span>}</h3>
            {(d.distribution ?? []).length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-8">No posted revenue yet.</p>
            ) : (
              <div className="space-y-3">
                {d.distribution.map((x: any) => (
                  <div key={x.head} className="flex items-center gap-3">
                    <span className="text-xs font-semibold text-slate-600 w-40 truncate shrink-0">{x.head}</span>
                    <div className="flex-1 h-6 bg-slate-100 rounded overflow-hidden"><div className="h-full bg-brand-500 rounded" style={{ width: `${Math.max(2, (Math.abs(x.amount) / maxDist) * 100)}%` }} /></div>
                    <span className="text-xs font-bold text-slate-700 w-28 text-right shrink-0">{formatCurrency(x.amount)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Bank Account Statements */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="mb-4"><h3 className="text-sm font-black uppercase tracking-widest text-slate-400 flex items-center gap-2"><Building2 size={15} /> Bank Account Statements</h3><p className="text-xs text-slate-400 mt-0.5">Current balance in each bank as of today</p></div>
            {(d.banks ?? []).length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-8">No bank accounts. Add them under Account Numbers and link each to its cash ledger account.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {d.banks.map((b: any) => (
                  <div key={b.id} className="rounded-xl border border-slate-200 p-4">
                    <p className="text-lg font-black text-slate-900">{formatCurrency(b.balance)}</p>
                    <p className="text-sm font-semibold text-slate-600 mt-1">{b.bank_name}</p>
                    <p className="text-xs text-slate-400">{b.account_number}</p>
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
