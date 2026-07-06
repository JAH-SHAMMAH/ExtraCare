"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useCreateRequisition, useAccounts, useFinanceSettings } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { ClipboardList, Plus, Trash2, Loader2, CheckCircle2, ArrowRight, ShieldCheck } from "lucide-react";

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

type LineRow = { description: string; quantity: string; unit_cost: string; note: string };
const emptyRow = (): LineRow => ({ description: "", quantity: "1", unit_cost: "", note: "" });

const CATEGORIES = ["supplies", "maintenance", "travel", "equipment", "services", "other"];

export default function RequestFormPage() {
  const canWrite = useHasPermission("payments:write");
  const { data: accounts } = useAccounts({ active_only: true });
  const { data: defaults } = useFinanceSettings();
  const create = useCreateRequisition();

  const [form, setForm] = useState({ title: "", department: "", category: "supplies", justification: "", notes: "", expense_account_id: "", settle_account_id: "" });
  const [items, setItems] = useState<LineRow[]>([emptyRow()]);
  const [submitted, setSubmitted] = useState(false);

  // Pre-fill accounts from Accounts Setup defaults (only if the user hasn't chosen).
  useEffect(() => {
    if (!defaults) return;
    setForm((f) => ({
      ...f,
      expense_account_id: f.expense_account_id || defaults.default_expense_account_id || "",
      settle_account_id: f.settle_account_id || defaults.default_cash_account_id || "",
    }));
  }, [defaults]);

  const expenseAccounts = useMemo(() => (accounts ?? []).filter((a) => a.type === "expense"), [accounts]);
  const settleAccounts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset" || a.type === "liability"), [accounts]);

  const lineAmount = (r: LineRow) => (Number(r.quantity) || 0) * (Number(r.unit_cost) || 0);
  const total = useMemo(() => items.reduce((s, r) => s + lineAmount(r), 0), [items]);
  const validRows = items.filter((r) => r.description.trim() && lineAmount(r) > 0);

  const canSubmit = form.title.trim() && form.expense_account_id && form.settle_account_id
    && form.expense_account_id !== form.settle_account_id && validRows.length > 0;

  const setRow = (i: number, patch: Partial<LineRow>) =>
    setItems((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  const reset = () => {
    setForm({ title: "", department: "", category: "supplies", justification: "", notes: "", expense_account_id: "", settle_account_id: "" });
    setItems([emptyRow()]);
  };

  const submit = () => {
    if (!canSubmit) return;
    create.mutate(
      {
        title: form.title.trim(),
        department: form.department.trim() || null,
        category: form.category || null,
        justification: form.justification.trim() || null,
        notes: form.notes.trim() || null,
        expense_account_id: form.expense_account_id,
        settle_account_id: form.settle_account_id,
        items: validRows.map((r) => ({ description: r.description.trim(), quantity: Number(r.quantity), unit_cost: Number(r.unit_cost), note: r.note.trim() || null })),
      },
      { onSuccess: () => { reset(); setSubmitted(true); } },
    );
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Request Form</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight">Request Form</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-6">Raise a purchase / expense requisition. It starts as a draft and enters the Requisitions approval queue — nothing is spent until an approver signs off.</p>

      {submitted && (
        <div className="flex items-center justify-between gap-3 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3 mb-5">
          <span className="inline-flex items-center gap-2"><CheckCircle2 size={16} /> Requisition submitted — it's now a draft awaiting approval.</span>
          <Link href="/dashboard/modules/school/requisitions" className="inline-flex items-center gap-1 font-semibold text-brand-600 hover:text-brand-700">View in Requisitions <ArrowRight size={14} /></Link>
        </div>
      )}

      {!canWrite ? (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-500"><ClipboardList size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">You don't have permission to raise requisitions.</p><p className="text-sm mt-1">Requires the <span className="font-mono">payments:write</span> permission.</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-5">
            <ShieldCheck size={14} className="mt-0.5 shrink-0" />
            <span>Two-person control: whoever approves this must be someone other than you. On approval it posts <span className="font-mono">Dr Expense / Cr Cash·Payable</span> to the ledger.</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="md:col-span-2"><label className="label">Title *</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" placeholder="e.g. Replace science-lab whiteboards" /></div>
            <div><label className="label">Department</label><input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className="input" placeholder="e.g. Science" /></div>
            <div>
              <label className="label">Category</label>
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="input capitalize">
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Expense account *</label>
              <select value={form.expense_account_id} onChange={(e) => setForm({ ...form, expense_account_id: e.target.value })} className="input">
                <option value="">Select account…</option>
                {expenseAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}
              </select>
              {expenseAccounts.length === 0 && <p className="text-[11px] text-amber-600 mt-1">No expense accounts yet — add one under Chart of Accounts.</p>}
            </div>
            <div>
              <label className="label">Fund from (cash / payable) *</label>
              <select value={form.settle_account_id} onChange={(e) => setForm({ ...form, settle_account_id: e.target.value })} className="input">
                <option value="">Select account…</option>
                {settleAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}
              </select>
            </div>
          </div>

          {/* Line items — grid (never an overflow-hidden / table wrapper). */}
          <label className="label">Items *</label>
          <div className="hidden md:grid grid-cols-12 gap-2 px-1 pb-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
            <div className="col-span-5">Description</div>
            <div className="col-span-2">Qty</div>
            <div className="col-span-2">Unit cost (₦)</div>
            <div className="col-span-2">Amount</div>
            <div className="col-span-1" />
          </div>
          <div className="space-y-2 mb-3">
            {items.map((r, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-center">
                <input value={r.description} onChange={(e) => setRow(i, { description: e.target.value })} className="input col-span-12 md:col-span-5" placeholder="What is being requested" />
                <input type="number" min="0" value={r.quantity} onChange={(e) => setRow(i, { quantity: e.target.value })} className="input col-span-4 md:col-span-2" placeholder="1" />
                <input type="number" min="0" value={r.unit_cost} onChange={(e) => setRow(i, { unit_cost: e.target.value })} className="input col-span-4 md:col-span-2" placeholder="0.00" />
                <div className="col-span-3 md:col-span-2 text-sm text-slate-700 tabular-nums">{naira(lineAmount(r))}</div>
                <div className="col-span-1 flex items-center justify-center">
                  {items.length > 1 && <button onClick={() => setItems((rows) => rows.filter((_, idx) => idx !== i))} className="text-slate-400 hover:text-red-600" title="Remove line"><Trash2 size={15} /></button>}
                </div>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mb-4">
            <button onClick={() => setItems((rows) => [...rows, emptyRow()])} className="btn-secondary gap-1.5 text-xs"><Plus size={13} /> Add item</button>
            <div className="text-sm text-slate-600">Total: <span className="font-bold text-slate-900">{naira(total)}</span></div>
          </div>

          <div className="mb-4"><label className="label">Justification (optional)</label><textarea value={form.justification} onChange={(e) => setForm({ ...form, justification: e.target.value })} className="input min-h-[70px]" placeholder="Why is this needed?" /></div>

          <div className="flex justify-end gap-3">
            <button onClick={reset} className="btn-secondary">Clear</button>
            <button onClick={submit} disabled={!canSubmit || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Submit requisition</button>
          </div>
        </div>
      )}
    </div>
  );
}
