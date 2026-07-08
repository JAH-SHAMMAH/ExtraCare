"use client";

import { useState } from "react";
import { useStatements } from "@/hooks/useFinance";
import { FileBarChart, AlertTriangle, Loader2, CheckCircle2 } from "lucide-react";

const fmt = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function FinancialStatementsPage() {
  const [asOf, setAsOf] = useState("");
  const { data, isLoading, isError, refetch } = useStatements(asOf ? { as_of: asOf } : undefined);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Financial Statements</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Financial Statements</h1>
          <p className="text-slate-500 text-sm mt-0.5">Trial balance, income statement and balance sheet — derived live from the ledger.</p>
        </div>
        <div><label className="label">As of</label><input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} className="input w-44" /></div>
      </div>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load statements.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : !data || data.trial_balance.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><FileBarChart size={36} className="mb-3 opacity-40" /><p className="font-semibold">No ledger activity yet</p><p className="text-sm mt-1">Post invoices, payroll or journal entries to populate the statements.</p></div>
      ) : (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <SummaryCard label="Net Income" value={data.net_income} sub={`Income ${fmt(data.income)} − Expense ${fmt(data.expense)}`} accent="from-emerald-500 to-teal-600" />
            <SummaryCard label="Total Assets" value={data.assets} sub="Debit-normal balances" accent="from-blue-500 to-indigo-600" />
            <SummaryCard label="Liabilities + Equity" value={data.liabilities + data.equity} sub={`Liab ${fmt(data.liabilities)} · Eq ${fmt(data.equity)}`} accent="from-fuchsia-500 to-purple-600" />
          </div>

          {/* Trial balance */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
              <h2 className="text-sm font-bold text-slate-800">Trial Balance</h2>
              <span className={data.balanced ? "inline-flex items-center gap-1 text-xs font-semibold text-emerald-600" : "text-xs font-semibold text-rose-600"}>{data.balanced && <CheckCircle2 size={13} />}{data.balanced ? "Balanced" : "Out of balance"}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Code", "Account", "Type", "Debit", "Credit"].map((h) => <th key={h} className="px-5 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
                <tbody className="divide-y divide-slate-50">
                  {data.trial_balance.map((r) => (
                    <tr key={r.account_id} className="hover:bg-slate-50/70">
                      <td className="px-5 py-2.5 text-sm font-mono text-slate-500">{r.code}</td>
                      <td className="px-5 py-2.5 text-sm text-slate-800">{r.name}</td>
                      <td className="px-5 py-2.5"><span className="badge bg-slate-50 text-slate-600 border-slate-200 capitalize">{r.type}</span></td>
                      <td className="px-5 py-2.5 text-sm text-slate-700">{r.debit ? fmt(r.debit) : "—"}</td>
                      <td className="px-5 py-2.5 text-sm text-slate-700">{r.credit ? fmt(r.credit) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot><tr className="border-t-2 border-slate-200 font-bold"><td colSpan={3} className="px-5 py-3 text-sm text-slate-700">Totals</td><td className="px-5 py-3 text-sm">{fmt(data.total_debit)}</td><td className="px-5 py-3 text-sm">{fmt(data.total_credit)}</td></tr></tfoot>
              </table>
            </div>
          </div>

          {/* Income statement + balance sheet */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h2 className="text-sm font-bold text-slate-800 mb-3">Income Statement</h2>
              <Row label="Income" value={data.income} />
              <Row label="Expense" value={data.expense} />
              <Row label="Net Income" value={data.net_income} bold />
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-bold text-slate-800">Balance Sheet</h2><span className={data.balance_sheet_balanced ? "text-xs font-semibold text-emerald-600" : "text-xs font-semibold text-rose-600"}>{data.balance_sheet_balanced ? "Balances ✓" : "Check"}</span></div>
              <Row label="Assets" value={data.assets} />
              <Row label="Liabilities" value={data.liabilities} />
              <Row label="Equity" value={data.equity} />
              <Row label="Net Income" value={data.net_income} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, sub, accent }: { label: string; value: number; sub: string; accent: string }) {
  return (
    <div className={`rounded-xl p-5 text-white bg-gradient-to-br ${accent}`}>
      <p className="text-2xl font-black">{fmt(value)}</p>
      <p className="text-sm font-semibold opacity-90">{label}</p>
      <p className="text-[11px] opacity-75 mt-1">{sub}</p>
    </div>
  );
}
function Row({ label, value, bold }: { label: string; value: number; bold?: boolean }) {
  return (
    <div className={`flex items-center justify-between py-2 border-b border-slate-50 ${bold ? "font-bold text-slate-900 border-t-2 border-slate-200" : "text-slate-600"}`}>
      <span className="text-sm">{label}</span><span className="text-sm">{fmt(value)}</span>
    </div>
  );
}
