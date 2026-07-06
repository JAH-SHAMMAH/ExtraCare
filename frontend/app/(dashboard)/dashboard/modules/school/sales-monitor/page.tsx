"use client";

import { useState } from "react";
import { useStoreSalesSummary } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { BarChart3, Loader2, AlertTriangle, TrendingUp, ShoppingCart, Receipt, Trophy, CreditCard, UserRound } from "lucide-react";

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const iso = (d: Date) => d.toISOString().slice(0, 10);

export default function SalesMonitorPage() {
  const canView = useHasPermission("payments:write");

  const now = new Date();
  const [start, setStart] = useState(iso(new Date(now.getFullYear(), now.getMonth(), 1)));
  const [end, setEnd] = useState(iso(now));

  const { data: rep, isLoading, isError, refetch, isFetching } = useStoreSalesSummary(
    canView ? { start: start || undefined, end: end || undefined } : undefined,
  );

  const preset = (kind: "month" | "year" | "all") => {
    if (kind === "all") { setStart(""); setEnd(""); return; }
    const d = new Date();
    if (kind === "month") { setStart(iso(new Date(d.getFullYear(), d.getMonth(), 1))); setEnd(iso(d)); }
    else { setStart(iso(new Date(d.getFullYear(), 0, 1))); setEnd(iso(d)); }
  };

  if (!canView) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-500">
          <BarChart3 size={36} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold">You don't have access to sales analytics.</p>
          <p className="text-sm mt-1">Store revenue reports require the <span className="font-mono">payments:write</span> permission.</p>
        </div>
      </div>
    );
  }

  const maxItem = Math.max(1, ...((rep?.top_items ?? []).map((i) => i.revenue)));

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Sales Monitor</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Sales Monitor</h1>
        <p className="text-slate-500 text-sm mt-0.5">Store sales for a period — revenue, top items, payment mix and cashier activity. (Voided sales are excluded.)</p>
      </div>

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
              <div className="flex items-center gap-2 text-emerald-600 mb-1"><TrendingUp size={16} /><span className="text-xs font-bold uppercase tracking-widest">Revenue</span></div>
              <p className="text-2xl font-black text-slate-900 tabular-nums">{naira(rep.total_revenue)}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-2 text-brand-600 mb-1"><ShoppingCart size={16} /><span className="text-xs font-bold uppercase tracking-widest">Sales</span></div>
              <p className="text-2xl font-black text-slate-900 tabular-nums">{rep.total_sales}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-2 text-slate-500 mb-1"><Receipt size={16} /><span className="text-xs font-bold uppercase tracking-widest">Avg sale</span></div>
              <p className="text-2xl font-black text-slate-900 tabular-nums">{naira(rep.average_sale)}</p>
            </div>
          </div>

          {rep.total_sales === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><Receipt size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No sales in this period</p></div>
          ) : (
            <div className="space-y-6">
              {/* Top items */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div className="px-5 py-3.5 border-b border-slate-100 text-sm font-bold text-slate-800 flex items-center gap-2"><Trophy size={15} className="text-amber-500" /> Top items</div>
                <div className="divide-y divide-slate-50">
                  {rep.top_items.map((it) => (
                    <div key={it.item_name} className="px-5 py-3">
                      <div className="flex items-center justify-between text-sm mb-1.5">
                        <span className="text-slate-700 font-medium">{it.item_name} <span className="text-[11px] text-slate-400">× {it.quantity}</span></span>
                        <span className="font-semibold text-slate-800 tabular-nums">{naira(it.revenue)}</span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden"><div className="h-full rounded-full bg-brand-500" style={{ width: `${(it.revenue / maxItem) * 100}%` }} /></div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* By payment */}
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="px-5 py-3.5 border-b border-slate-100 text-sm font-bold text-slate-800 flex items-center gap-2"><CreditCard size={15} /> By payment method</div>
                  <div className="divide-y divide-slate-50">
                    {rep.by_payment.map((g) => (
                      <div key={g.key} className="flex items-center justify-between px-5 py-3 text-sm">
                        <span className="text-slate-700">{g.label} <span className="text-[11px] text-slate-400">({g.count})</span></span>
                        <span className="font-semibold text-slate-800 tabular-nums">{naira(g.revenue)}</span>
                      </div>
                    ))}
                  </div>
                </div>
                {/* By cashier */}
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="px-5 py-3.5 border-b border-slate-100 text-sm font-bold text-slate-800 flex items-center gap-2"><UserRound size={15} /> By cashier</div>
                  <div className="divide-y divide-slate-50">
                    {rep.by_cashier.map((g) => (
                      <div key={g.key} className="flex items-center justify-between px-5 py-3 text-sm">
                        <span className="text-slate-700">{g.label} <span className="text-[11px] text-slate-400">({g.count})</span></span>
                        <span className="font-semibold text-slate-800 tabular-nums">{naira(g.revenue)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
