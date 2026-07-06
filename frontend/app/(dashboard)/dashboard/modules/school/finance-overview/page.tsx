"use client";

import { useMemo } from "react";
import { useStatements, useInvoices, usePayrollRuns, useCashTxns } from "@/hooks/useFinance";
import { cn, formatDate } from "@/lib/utils";
import { TrendingUp, Receipt, BadgeDollarSign, Wallet, AlertTriangle } from "lucide-react";

const fmt = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function FinanceOverviewPage() {
  const { data: stmt, isLoading: sl, isError: se, refetch } = useStatements();
  const { data: invoices } = useInvoices();
  const { data: payroll } = usePayrollRuns();
  const { data: cash } = useCashTxns();

  const inv = useMemo(() => {
    const items = invoices?.items ?? [];
    const by = (s: string) => items.filter((i) => i.status === s);
    const outstanding = by("posted").reduce((s, i) => s + Number(i.total), 0);
    return { total: items.length, draft: by("draft").length, posted: by("posted").length, paid: by("paid").length, outstanding };
  }, [invoices]);

  const payrollTotal = useMemo(() => (payroll?.items ?? []).reduce((s, r) => s + Number(r.total_net), 0), [payroll]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Broad View</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">Broad View <span className="text-[9px] font-bold uppercase bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">beta</span></h1>
        <p className="text-slate-500 text-sm mt-0.5">A consolidated snapshot across the ledger, invoicing and payroll.</p>
      </div>

      {se ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load the overview.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <Stat icon={TrendingUp} label="Net Income" value={sl ? null : fmt(stmt?.net_income ?? 0)} accent="from-emerald-500 to-teal-600" />
            <Stat icon={Wallet} label="Total Assets" value={sl ? null : fmt(stmt?.assets ?? 0)} accent="from-blue-500 to-indigo-600" />
            <Stat icon={Receipt} label="Outstanding Invoices" value={fmt(inv.outstanding)} accent="from-rose-500 to-pink-600" />
            <Stat icon={BadgeDollarSign} label="Payroll (net, all runs)" value={fmt(payrollTotal)} accent="from-fuchsia-500 to-purple-600" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h2 className="text-sm font-bold text-slate-800 mb-4">Invoices</h2>
              <div className="grid grid-cols-4 gap-2 text-center">
                {[["Draft", inv.draft, "text-slate-500"], ["Posted", inv.posted, "text-blue-600"], ["Paid", inv.paid, "text-emerald-600"], ["Total", inv.total, "text-slate-800"]].map(([l, v, c]) => (
                  <div key={l as string}><p className={cn("text-xl font-black", c as string)}>{v as number}</p><p className="text-[10px] font-bold uppercase text-slate-400">{l as string}</p></div>
                ))}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h2 className="text-sm font-bold text-slate-800 mb-4">Recent cash movements</h2>
              {(cash?.items ?? []).length === 0 ? (
                <p className="text-sm text-slate-400 py-6 text-center">No cash transactions yet.</p>
              ) : (
                <div className="divide-y divide-slate-50">
                  {(cash?.items ?? []).slice(0, 5).map((t: any) => (
                    <div key={t.id} className="flex items-center justify-between py-2">
                      <span className="text-sm text-slate-600 truncate">{t.memo || t.type}</span>
                      <span className={cn("text-sm font-semibold", t.type === "receipt" ? "text-emerald-600" : "text-rose-600")}>{t.type === "receipt" ? "+" : "−"}{fmt(Number(t.amount))}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {!sl && stmt && (
            <p className="text-xs text-slate-400 mt-4">Ledger {stmt.balanced ? "balanced ✓" : "out of balance — review journal"}. Figures derive live from posted entries.</p>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value, accent }: { icon: any; label: string; value: string | null; accent: string }) {
  return (
    <div className={`rounded-xl p-5 text-white bg-gradient-to-br ${accent}`}>
      <Icon size={18} className="opacity-80 mb-2" />
      {value === null ? <div className="h-7 w-24 bg-white/30 rounded animate-pulse" /> : <p className="text-2xl font-black">{value}</p>}
      <p className="text-xs font-semibold opacity-90 mt-1">{label}</p>
    </div>
  );
}
