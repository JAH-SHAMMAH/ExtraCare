"use client";

import { useMemo, useState } from "react";
import { useIncomeExpenseReport } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { BarChart3, Download, Loader2, AlertTriangle, TrendingUp, TrendingDown, Scale } from "lucide-react";
import type { IncomeExpenseReport } from "@/types";

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const iso = (d: Date) => d.toISOString().slice(0, 10);

const SOURCE_LABEL: Record<string, string> = {
  payroll: "Payroll", requisition: "Requisitions", pay_adjustment: "Bonus / Reduction",
  petty_cash: "Petty cash", cash: "Cash txns", invoice: "Invoices / fees", store: "Store",
  salary_advance: "Salary advance", salary_advance_repay: "Advance repayment", manual: "Manual", reversal: "Reversals",
};
const sourceLabel = (s: string) => SOURCE_LABEL[s] ?? s;

function toCsv(rep: IncomeExpenseReport): string {
  const q = (s: string) => `"${String(s).replace(/"/g, '""')}"`;
  const L: string[] = [];
  L.push("Income & Expense Report");
  L.push(`Period,${rep.start || "All-time"},${rep.end || ""}`);
  L.push("");
  L.push("Summary,Amount");
  L.push(`Income,${rep.income}`);
  L.push(`Expense,${rep.expense}`);
  L.push(`Net,${rep.net}`);
  L.push("");
  L.push("By account");
  L.push("Code,Name,Type,Amount");
  rep.by_account.forEach((r) => L.push(`${q(r.code)},${q(r.name)},${r.type},${r.amount}`));
  L.push("");
  L.push("By source");
  L.push("Source,Income,Expense");
  rep.by_source.forEach((r) => L.push(`${q(sourceLabel(r.source))},${r.income},${r.expense}`));
  return L.join("\n");
}

export default function FinanceReportsPage() {
  const canView = useHasPermission("payments:write");

  const now = new Date();
  const [start, setStart] = useState(iso(new Date(now.getFullYear(), 0, 1)));
  const [end, setEnd] = useState(iso(now));

  const { data: rep, isLoading, isError, refetch, isFetching } = useIncomeExpenseReport(
    canView ? { start: start || undefined, end: end || undefined } : undefined,
  );

  const income = rep?.by_account.filter((r) => r.type === "income") ?? [];
  const expenses = rep?.by_account.filter((r) => r.type === "expense") ?? [];

  const preset = (kind: "month" | "year" | "all") => {
    if (kind === "all") { setStart(""); setEnd(""); return; }
    const d = new Date();
    if (kind === "month") { setStart(iso(new Date(d.getFullYear(), d.getMonth(), 1))); setEnd(iso(d)); }
    else { setStart(iso(new Date(d.getFullYear(), 0, 1))); setEnd(iso(d)); }
  };

  const download = () => {
    if (!rep) return;
    const blob = new Blob([toCsv(rep)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `income-expense_${rep.start || "all"}_${rep.end || "now"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!canView) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-500">
          <BarChart3 size={36} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold">You don't have access to finance reports.</p>
          <p className="text-sm mt-1">School-wide financial reports require the <span className="font-mono">payments:write</span> permission.</p>
        </div>
      </div>
    );
  }

  const netPositive = (rep?.net ?? 0) >= 0;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Reports</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Finance Reports</h1>
          <p className="text-slate-500 text-sm mt-0.5">Income &amp; expense for a period, from the ledger — broken down by account and by what drove it.</p>
        </div>
        <button onClick={download} disabled={!rep} className="btn-secondary gap-2 disabled:opacity-50"><Download size={15} /> Export CSV</button>
      </div>

      {/* Period controls */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex flex-wrap items-end gap-4">
        <div><label className="label">From</label><input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="input" /></div>
        <div><label className="label">To</label><input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="input" /></div>
        <div className="flex items-center gap-2 pb-0.5">
          <button onClick={() => preset("month")} className="btn-secondary text-xs">This month</button>
          <button onClick={() => preset("year")} className="btn-secondary text-xs">This year</button>
          <button onClick={() => preset("all")} className="btn-secondary text-xs">All time</button>
        </div>
        {isFetching && <Loader2 size={16} className="animate-spin text-slate-400 ml-auto" />}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load the report.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rep ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-2 text-emerald-600 mb-1"><TrendingUp size={16} /><span className="text-xs font-bold uppercase tracking-widest">Income</span></div>
              <p className="text-2xl font-black text-slate-900 tabular-nums">{naira(rep.income)}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-2 text-rose-600 mb-1"><TrendingDown size={16} /><span className="text-xs font-bold uppercase tracking-widest">Expense</span></div>
              <p className="text-2xl font-black text-slate-900 tabular-nums">{naira(rep.expense)}</p>
            </div>
            <div className={cn("rounded-xl border p-5", netPositive ? "bg-emerald-50 border-emerald-200" : "bg-rose-50 border-rose-200")}>
              <div className={cn("flex items-center gap-2 mb-1", netPositive ? "text-emerald-700" : "text-rose-700")}><Scale size={16} /><span className="text-xs font-bold uppercase tracking-widest">Net {netPositive ? "surplus" : "deficit"}</span></div>
              <p className={cn("text-2xl font-black tabular-nums", netPositive ? "text-emerald-800" : "text-rose-800")}>{naira(rep.net)}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* By account */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-5 py-3.5 border-b border-slate-100 text-sm font-bold text-slate-800">By account</div>
              {income.length === 0 && expenses.length === 0 ? (
                <p className="px-5 py-8 text-center text-sm text-slate-400">No activity in this period.</p>
              ) : (
                <div className="divide-y divide-slate-50">
                  {income.map((r) => (
                    <div key={r.account_id} className="flex items-center justify-between px-5 py-3 text-sm">
                      <span className="text-slate-700">{r.code} {r.name} <span className="ml-1 text-[10px] font-bold uppercase text-emerald-600">income</span></span>
                      <span className="font-semibold text-slate-800 tabular-nums">{naira(r.amount)}</span>
                    </div>
                  ))}
                  {expenses.map((r) => (
                    <div key={r.account_id} className="flex items-center justify-between px-5 py-3 text-sm">
                      <span className="text-slate-700">{r.code} {r.name} <span className="ml-1 text-[10px] font-bold uppercase text-rose-600">expense</span></span>
                      <span className="font-semibold text-slate-800 tabular-nums">{naira(r.amount)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* By source */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-5 py-3.5 border-b border-slate-100 text-sm font-bold text-slate-800">By source</div>
              {rep.by_source.length === 0 ? (
                <p className="px-5 py-8 text-center text-sm text-slate-400">No activity in this period.</p>
              ) : (
                <div className="divide-y divide-slate-50">
                  <div className="grid grid-cols-12 px-5 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                    <div className="col-span-6">Source</div><div className="col-span-3 text-right">Income</div><div className="col-span-3 text-right">Expense</div>
                  </div>
                  {rep.by_source.map((r) => (
                    <div key={r.source} className="grid grid-cols-12 px-5 py-3 text-sm items-center">
                      <div className="col-span-6 text-slate-700">{sourceLabel(r.source)}</div>
                      <div className="col-span-3 text-right tabular-nums text-emerald-700">{r.income ? naira(r.income) : "—"}</div>
                      <div className="col-span-3 text-right tabular-nums text-rose-700">{r.expense ? naira(r.expense) : "—"}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
