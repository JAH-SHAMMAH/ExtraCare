"use client";

import { useState } from "react";
import Link from "next/link";
import { useFeeRecords, usePrimaryBankAccount } from "@/hooks/useFinance";
import { cn, formatDate, formatCurrency } from "@/lib/utils";
import { Wallet, Search, Landmark, ArrowUpRight, AlertTriangle } from "lucide-react";
import type { FeeRecord } from "@/types";

/**
 * Fee Management — collections overview. A read-focused window onto the real
 * StudentFeeRecord data (GET /finance/fee-records): what every student has been
 * billed, paid, discounted, and still owes. Assigning/editing fees lives in Fee
 * Assignment (the single write path); recording a payment against a record has no
 * backend yet, so this surface intentionally does neither — it reports, it doesn't
 * mutate.
 */

const STATUS_STYLE: Record<string, string> = {
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  partial: "bg-amber-50 text-amber-700 border-amber-200",
  unpaid: "bg-red-50 text-red-700 border-red-200",
};

type StatusTab = "all" | "unpaid" | "partial" | "paid";

function isOverdue(f: FeeRecord): boolean {
  return !!f.due_date && f.outstanding_balance > 0 && new Date(f.due_date) < new Date();
}

export default function FeesPage() {
  const [tab, setTab] = useState<StatusTab>("all");
  const [search, setSearch] = useState("");

  const { data, isLoading } = useFeeRecords();
  const { data: payTo } = usePrimaryBankAccount();

  const items: FeeRecord[] = data ?? [];

  // Summary reflects the whole roster, not the active filter.
  const totalBilled = items.reduce((s, f) => s + (f.total_fee || 0), 0);
  const totalCollected = items.reduce((s, f) => s + (f.paid_amount || 0), 0);
  const totalOutstanding = items.reduce((s, f) => s + (f.outstanding_balance || 0), 0);
  const collectionRate = totalBilled > 0 ? Math.round((totalCollected / totalBilled) * 100) : 0;

  const filtered = items.filter((f) => {
    const matchStatus = tab === "all" || f.payment_status === tab;
    const matchSearch = !search || (f.student_name || f.student_id || "").toLowerCase().includes(search.toLowerCase());
    return matchStatus && matchSearch;
  });

  const summary = [
    { label: "Total Billed", value: formatCurrency(totalBilled) },
    { label: "Collected", value: formatCurrency(totalCollected) },
    { label: "Outstanding", value: formatCurrency(totalOutstanding) },
    { label: "Collection Rate", value: `${collectionRate}%` },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Fee Management</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Fee Management</h1>
          <p className="text-slate-500 text-sm mt-0.5">Collections overview — what every student has been billed and still owes.</p>
        </div>
        <Link href="/dashboard/modules/school/fee-assignment" className="btn-secondary gap-2">
          <ArrowUpRight size={15} /> Assign / edit fees
        </Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {summary.map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
            <p className="text-xl font-black text-slate-900 tabular-nums">{value}</p>
          </div>
        ))}
      </div>

      {payTo && (
        <div className="bg-brand-50 border border-brand-200 rounded-xl p-4 mb-6 flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-brand-100 flex items-center justify-center shrink-0"><Landmark size={18} className="text-brand-700" /></div>
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-widest text-brand-700 mb-0.5">Pay fees to</p>
            <p className="text-sm font-bold text-slate-900">{payTo.bank_name} · <span className="font-mono">{payTo.account_number}</span></p>
            <p className="text-xs text-slate-600">{payTo.account_name}{payTo.bank_code ? ` · ${payTo.bank_code}` : ""}{payTo.account_type ? ` · ${payTo.account_type}` : ""}{payTo.purpose ? ` · ${payTo.purpose}` : ""}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="flex gap-2 flex-wrap">
          {(["all", "unpaid", "partial", "paid"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize", tab === t ? "bg-brand-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50")}>{t}</button>
          ))}
        </div>
        <div className="relative sm:ml-auto sm:w-64">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search student…" className="input pl-9 w-full" />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Term / Session", "Billed", "Discount", "Paid", "Outstanding", "Status", "Due Date"].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 5 }).map((_, i) => (<tr key={i}><td colSpan={8} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-48" /></td></tr>))
            : filtered.length === 0 ? (<tr><td colSpan={8} className="px-5 py-16 text-center text-slate-400 text-sm"><Wallet size={32} className="mx-auto mb-2 opacity-50" />No fee records found. Assign fees in <Link href="/dashboard/modules/school/fee-assignment" className="text-brand-600 font-semibold hover:underline">Fee Assignment</Link>.</td></tr>)
            : filtered.map((f) => {
              const overdue = isOverdue(f);
              return (
                <tr key={f.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="px-5 py-3.5 text-sm font-bold text-slate-900 whitespace-nowrap">{f.student_name || f.student_id}</td>
                  <td className="px-5 py-3.5 text-xs text-slate-500 whitespace-nowrap">{f.term}<span className="text-slate-300"> · </span>{f.session_year}</td>
                  <td className="px-5 py-3.5 text-sm font-medium text-slate-800 tabular-nums">{formatCurrency(f.total_fee)}</td>
                  <td className="px-5 py-3.5 text-sm text-slate-500 tabular-nums">{f.discount_amount ? formatCurrency(f.discount_amount) : "—"}</td>
                  <td className="px-5 py-3.5 text-sm text-emerald-600 tabular-nums">{formatCurrency(f.paid_amount)}</td>
                  <td className="px-5 py-3.5 text-sm text-red-600 font-medium tabular-nums">{formatCurrency(f.outstanding_balance)}</td>
                  <td className="px-5 py-3.5"><span className={cn("badge capitalize", STATUS_STYLE[f.payment_status] || "bg-slate-50 text-slate-600 border-slate-200")}>{f.payment_status}</span></td>
                  <td className={cn("px-5 py-3.5 text-xs whitespace-nowrap", overdue ? "text-red-600 font-semibold" : "text-slate-500")}>
                    {f.due_date ? (
                      <span className="inline-flex items-center gap-1">{overdue && <AlertTriangle size={12} />}{formatDate(f.due_date)}</span>
                    ) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
