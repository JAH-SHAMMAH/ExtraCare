"use client";

import { useMemo, useState } from "react";
import { usePocketMoneyStudents, usePocketMoneyItems, useCreatePMTransaction } from "@/hooks/useWallet";
import { useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatCurrency } from "@/lib/utils";
import {
  ShoppingCart, Search, Loader2, AlertTriangle, X, Plus, Trash2, Lock, ChevronLeft, ChevronRight, Receipt,
} from "lucide-react";
import type { PocketMoneyStudentRow } from "@/types";

const PAGE_SIZE = 20;

export default function NewPocketMoneyTransactionPage() {
  const canSpend = useHasPermission("wallet:spend");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = usePocketMoneyStudents({ page, page_size: PAGE_SIZE, search: search || undefined });
  const [cartFor, setCartFor] = useState<PocketMoneyStudentRow | null>(null);

  const rows = data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));
  const onSearch = (v: string) => { setSearch(v); setPage(1); };

  if (!canSpend) return (
    <div className="p-8 max-w-2xl mx-auto"><div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><Lock size={30} className="mx-auto mb-3 opacity-50" /><p className="font-semibold text-slate-600">Recording a transaction requires the wallet:spend permission.</p></div></div>
  );

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>PocketMoney Manager</span><span>/</span><span className="text-brand-600 font-semibold">New Transaction</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">New Transaction</h1>
        <p className="text-slate-500 text-sm mt-0.5">Pick a student and record a canteen purchase. Balances are ledger-derived; no overdraw.</p>
      </div>

      <div className="bg-brand-700 rounded-t-xl px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
        <p className="text-white font-bold text-sm flex items-center gap-2"><ShoppingCart size={16} /> Pocket Money Student List</p>
        <span className="text-xs font-semibold text-white bg-white/15 rounded-lg px-3 py-1.5">Total Transactions Today: <span className="font-black">{formatCurrency(data?.today_total ?? 0)}</span></span>
      </div>

      <div className="bg-white rounded-b-xl border border-slate-200 border-t-0">
        <div className="p-4 border-b border-slate-100">
          <div className="relative max-w-sm"><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => onSearch(e.target.value)} placeholder="Search students…" className="input pl-9" /></div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Student Name", "Parent Name", "Class", "Current Pocket Money Balance", "Action"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
              ) : isError ? (
                <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load students.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
              ) : rows.length > 0 ? (
                rows.map((s, i) => (
                  <tr key={s.student_id} className="hover:bg-slate-50/70">
                    <td className="px-5 py-3 text-sm text-slate-500">{(page - 1) * PAGE_SIZE + i + 1}</td>
                    <td className="px-5 py-3 text-sm font-semibold text-slate-800 whitespace-nowrap">{s.student_name}</td>
                    <td className="px-5 py-3 text-sm text-slate-600 whitespace-nowrap">{s.parent_name || <span className="text-slate-300">—</span>}</td>
                    <td className="px-5 py-3 text-sm text-slate-600 whitespace-nowrap">{s.class_name || <span className="text-slate-300">—</span>}</td>
                    <td className="px-5 py-3"><span className="inline-block bg-amber-50 text-amber-800 border border-amber-100 rounded px-2.5 py-1 text-sm font-bold">{formatCurrency(s.balance)}</span></td>
                    <td className="px-5 py-3">
                      <button onClick={() => setCartFor(s)} title="New transaction" className="w-9 h-9 rounded-lg bg-teal-500 hover:bg-teal-600 text-white flex items-center justify-center"><ShoppingCart size={16} /></button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={6} className="py-16 text-center text-slate-400"><ShoppingCart size={34} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No students found</p></td></tr>
              )}
            </tbody>
          </table>
        </div>
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 text-sm">
            <span className="text-slate-400">Page {page} of {totalPages} · {data?.total} students</span>
            <div className="flex gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="btn-secondary gap-1 py-1.5 disabled:opacity-40"><ChevronLeft size={14} /> Prev</button>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="btn-secondary gap-1 py-1.5 disabled:opacity-40">Next <ChevronRight size={14} /></button>
            </div>
          </div>
        )}
      </div>

      {cartFor && <PurchaseModal student={cartFor} onClose={() => setCartFor(null)} />}
    </div>
  );
}

type Line = { item_id: string; qty: number };

function PurchaseModal({ student, onClose }: { student: PocketMoneyStudentRow; onClose: () => void }) {
  const { data: items } = usePocketMoneyItems(true);
  const { data: accounts } = useAccounts({ active_only: true });
  const create = useCreatePMTransaction();

  const incomeAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "income"), [accounts]);
  const itemList = items ?? [];
  const priceOf = (id: string) => itemList.find((i) => i.id === id)?.unit_price ?? 0;

  const [lines, setLines] = useState<Line[]>([]);
  const [directAmount, setDirectAmount] = useState("");
  const [incomeId, setIncomeId] = useState("");
  const [memo, setMemo] = useState("");

  // Default the income account to the first available once loaded.
  const income = incomeId || (incomeAccts[0]?.id ?? "");
  const total = lines.reduce((s, l) => s + priceOf(l.item_id) * l.qty, 0);
  const effectiveAmount = lines.length > 0 ? total : Number(directAmount || 0);
  const canSubmit = income && effectiveAmount > 0 && (lines.length === 0 || lines.every((l) => l.item_id));

  const submit = () => {
    const data: any = { student_id: student.student_id, income_account_id: income, memo: memo || null };
    if (lines.length > 0) data.lines = lines.filter((l) => l.item_id).map((l) => ({ item_id: l.item_id, qty: l.qty }));
    else data.amount = Number(directAmount);
    create.mutate(data, { onSuccess: onClose });
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div><h3 className="text-sm font-bold text-slate-800">New Transaction — {student.student_name}</h3><p className="text-xs text-slate-400">{student.parent_name || ""} · balance {formatCurrency(student.balance)}</p></div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
        </div>
        <div className="px-6 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          <div>
            <div className="flex items-center justify-between mb-2"><label className="label mb-0">Items</label><button onClick={() => setLines([...lines, { item_id: "", qty: 1 }])} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700"><Plus size={13} /> Add item</button></div>
            {lines.length === 0 ? <p className="text-xs text-slate-400">No items — or enter a direct amount below.</p> : (
              <div className="space-y-2">
                {lines.map((l, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <select value={l.item_id} onChange={(e) => setLines(lines.map((x, i) => i === idx ? { ...x, item_id: e.target.value } : x))} className="input flex-1"><option value="">Select item…</option>{itemList.map((it) => <option key={it.id} value={it.id}>{it.name} — {it.unit_price.toFixed(2)}</option>)}</select>
                    <input type="number" min={1} value={l.qty} onChange={(e) => setLines(lines.map((x, i) => i === idx ? { ...x, qty: Math.max(1, Number(e.target.value)) } : x))} className="input w-20" />
                    <span className="text-sm font-semibold text-slate-600 w-24 text-right">{formatCurrency(priceOf(l.item_id) * l.qty)}</span>
                    <button onClick={() => setLines(lines.filter((_, i) => i !== idx))} className="text-rose-400 hover:text-rose-600 p-1"><Trash2 size={15} /></button>
                  </div>
                ))}
                <div className="flex justify-end pt-1 text-sm font-bold text-slate-800">Total: {formatCurrency(total)}</div>
              </div>
            )}
          </div>
          {lines.length === 0 && <div><label className="label">Or amount directly *</label><input type="number" value={directAmount} onChange={(e) => setDirectAmount(e.target.value)} className="input" placeholder="0.00" /></div>}
          <div><label className="label">Sold as (income account) *</label><select value={income} onChange={(e) => setIncomeId(e.target.value)} className="input"><option value="">Select…</option>{incomeAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
          <div><label className="label">Memo</label><input value={memo} onChange={(e) => setMemo(e.target.value)} className="input" placeholder="optional — defaults to the item list" /></div>
        </div>
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100">
          <span className="text-sm text-slate-500">Charge: <span className="font-bold text-slate-900">{formatCurrency(effectiveAmount)}</span></span>
          <button onClick={submit} disabled={!canSubmit || create.isPending} className="btn-primary gap-2">{create.isPending ? <Loader2 size={15} className="animate-spin" /> : <Receipt size={15} />} Record</button>
        </div>
      </div>
    </div>
  );
}
