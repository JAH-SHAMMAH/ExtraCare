"use client";

import { useMemo, useState } from "react";
import { useBudgets, useCreateBudget, useUpdateBudget, useDeleteBudget, useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { PiggyBank, Plus, X, Loader2, Trash2, Pencil, AlertTriangle } from "lucide-react";
import type { Budget } from "@/types";

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

type FormState = { account_id: string; period_label: string; start_date: string; end_date: string; amount: string; notes: string };
const emptyForm = (): FormState => ({ account_id: "", period_label: "", start_date: "", end_date: "", amount: "", notes: "" });

export default function BudgetMgtPage() {
  const canWrite = useHasPermission("payments:write");
  const { data: budgets, isLoading, isError, refetch } = useBudgets();
  const { data: accounts } = useAccounts({ active_only: true });
  const create = useCreateBudget();
  const update = useUpdateBudget();
  const del = useDeleteBudget();

  const expenseAccounts = useMemo(() => (accounts ?? []).filter((a) => a.type === "expense"), [accounts]);

  const [show, setShow] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());

  const openCreate = () => { setEditingId(null); setForm(emptyForm()); setShow(true); };
  const openEdit = (b: Budget) => {
    setEditingId(b.id);
    setForm({ account_id: b.account_id, period_label: b.period_label ?? "", start_date: b.start_date ?? "", end_date: b.end_date ?? "", amount: String(b.amount), notes: b.notes ?? "" });
    setShow(true);
  };
  const close = () => { setShow(false); setEditingId(null); setForm(emptyForm()); };

  const datesValid = !form.start_date || !form.end_date || form.end_date >= form.start_date;
  const canSubmit = form.account_id && Number(form.amount) >= 0 && datesValid;

  const submit = () => {
    if (!canSubmit) return;
    const payload = {
      period_label: form.period_label.trim() || null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      amount: Number(form.amount),
      notes: form.notes.trim() || null,
    };
    if (editingId) {
      update.mutate({ id: editingId, data: payload }, { onSuccess: close });
    } else {
      create.mutate({ account_id: form.account_id, ...payload }, { onSuccess: close });
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Budget Mgt</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Budget Management</h1>
          <p className="text-slate-500 text-sm mt-0.5">Set a spending budget per expense account and period. Spend is measured live from the ledger within the period window.</p>
        </div>
        {canWrite && <button onClick={openCreate} className="btn-primary gap-2"><Plus size={15} /> New Budget</button>}
      </div>

      <p className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mb-5">Budgets are a soft control — overspend is flagged here, never blocked. Give a budget a start &amp; end date to track spend for just that period; leave dates blank to track all-time spend on the account.</p>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editingId ? "Edit budget" : "New budget"}</h2><button onClick={close} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="md:col-span-2">
              <label className="label">Expense account *</label>
              <select value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })} disabled={!!editingId} className="input disabled:bg-slate-50 disabled:text-slate-500">
                <option value="">Select account…</option>
                {expenseAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}
              </select>
              {!editingId && expenseAccounts.length === 0 && <p className="text-[11px] text-amber-600 mt-1">No expense accounts yet — add one under Chart of Accounts.</p>}
              {editingId && <p className="text-[11px] text-slate-400 mt-1">The account can't be changed on an existing budget.</p>}
            </div>
            <div><label className="label">Period label</label><input value={form.period_label} onChange={(e) => setForm({ ...form, period_label: e.target.value })} className="input" placeholder="e.g. 2026 Q1" /></div>
            <div><label className="label">Budget amount (₦) *</label><input type="number" min="0" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="input" placeholder="100000" /></div>
            <div><label className="label">Start date</label><input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="input" /></div>
            <div><label className="label">End date</label><input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className={cn("input", !datesValid && "border-rose-300")} /></div>
            <div className="md:col-span-2"><label className="label">Notes</label><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" placeholder="optional" /></div>
          </div>
          {!datesValid && <p className="text-xs text-rose-600 mb-3">End date can't be before the start date.</p>}
          <div className="flex justify-end gap-3"><button onClick={close} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!canSubmit || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}{editingId ? "Save changes" : "Set budget"}</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load budgets.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : budgets && budgets.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {budgets.map((b: Budget) => {
            const pct = b.amount > 0 ? (b.spent / b.amount) * 100 : (b.spent > 0 ? 100 : 0);
            const over = b.remaining < 0;
            const near = !over && pct >= 80;
            const barColor = over ? "bg-rose-500" : near ? "bg-amber-500" : "bg-emerald-500";
            const window = b.start_date || b.end_date
              ? `${b.start_date ? formatDate(b.start_date) : "…"} – ${b.end_date ? formatDate(b.end_date) : "…"}`
              : "All-time (no dates)";
            return (
              <div key={b.id} className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="font-bold text-slate-800">{b.account_name || b.account_id.slice(0, 8)}</p>
                    <p className="text-[11px] text-slate-400">{b.period_label ? `${b.period_label} · ` : ""}{window}</p>
                  </div>
                  {canWrite && (
                    <div className="flex items-center gap-1">
                      <button onClick={() => openEdit(b)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Pencil size={14} /></button>
                      <button onClick={() => { if (confirm("Remove this budget?")) del.mutate(b.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Remove"><Trash2 size={14} /></button>
                    </div>
                  )}
                </div>
                <div className="flex items-end justify-between mb-1.5 text-sm">
                  <span className="text-slate-500">Spent <span className="font-semibold text-slate-800">{naira(b.spent)}</span></span>
                  <span className="text-slate-500">of {naira(b.amount)}</span>
                </div>
                <div className="h-2.5 w-full rounded-full bg-slate-100 overflow-hidden mb-2">
                  <div className={cn("h-full rounded-full transition-all", barColor)} style={{ width: `${Math.min(pct, 100)}%` }} />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className={cn("font-semibold", over ? "text-rose-600" : near ? "text-amber-600" : "text-emerald-600")}>{pct.toFixed(0)}% used</span>
                  <span className={cn("font-semibold", over ? "text-rose-600" : "text-slate-600")}>{over ? `${naira(-b.remaining)} over` : `${naira(b.remaining)} left`}</span>
                </div>
                {b.notes && <p className="text-[11px] text-slate-400 mt-2">{b.notes}</p>}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><PiggyBank size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No budgets yet</p>{canWrite && <button onClick={openCreate} className="text-brand-600 hover:text-brand-700 text-sm font-semibold mt-1">Set your first budget →</button>}</div>
      )}
    </div>
  );
}
