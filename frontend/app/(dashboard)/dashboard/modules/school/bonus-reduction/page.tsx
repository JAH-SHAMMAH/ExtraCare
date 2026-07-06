"use client";

import { useEffect, useMemo, useState } from "react";
import {
  usePayAdjustments, useCreatePayAdjustment, useApprovePayAdjustment,
  useVoidPayAdjustment, useDeletePayAdjustment, useAccounts, useFinanceSettings,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import {
  Gift, Plus, X, Loader2, Trash2, AlertTriangle, CheckCircle2, Ban, ShieldCheck, MinusCircle, PlusCircle,
} from "lucide-react";
import type { PayAdjustmentPack } from "@/types";

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600 border-slate-200",
  approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  void: "bg-rose-50 text-rose-700 border-rose-200",
};
const KIND_STYLE: Record<string, string> = {
  bonus: "bg-emerald-50 text-emerald-700 border-emerald-200",
  reduction: "bg-amber-50 text-amber-700 border-amber-200",
};

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

type ItemRow = { staff_user_id: string; staff_name: string; amount: string; note: string };
const emptyRow = (): ItemRow => ({ staff_user_id: "", staff_name: "", amount: "", note: "" });

export default function BonusReductionPage() {
  const canWrite = useHasPermission("payments:write");
  const canPost = useHasPermission("payments:post");
  const [kindFilter, setKindFilter] = useState("");
  const [show, setShow] = useState(false);

  const { data: packs, isLoading, isError, refetch } = usePayAdjustments(kindFilter ? { kind: kindFilter } : undefined);
  const { data: accounts } = useAccounts({ active_only: true });
  const { data: defaults } = useFinanceSettings();
  const create = useCreatePayAdjustment();
  const approve = useApprovePayAdjustment();
  const voidPack = useVoidPayAdjustment();
  const del = useDeletePayAdjustment();

  const [form, setForm] = useState<{ label: string; kind: "bonus" | "reduction"; reason: string; expense_account_id: string; settle_account_id: string }>(
    { label: "", kind: "bonus", reason: "", expense_account_id: "", settle_account_id: "" },
  );
  const [items, setItems] = useState<ItemRow[]>([emptyRow()]);

  // Pre-fill accounts from Accounts Setup defaults (only if unset). The P&L default
  // follows the kind: bonus → expense, reduction → income.
  useEffect(() => {
    if (!defaults) return;
    setForm((f) => ({
      ...f,
      settle_account_id: f.settle_account_id || defaults.default_cash_account_id || "",
      expense_account_id: f.expense_account_id || (f.kind === "bonus" ? (defaults.default_expense_account_id || "") : (defaults.default_income_account_id || "")),
    }));
  }, [defaults, form.kind]);

  // Bonus posts to an EXPENSE account; a reduction offsets to an INCOME account.
  const plAccounts = useMemo(
    () => (accounts ?? []).filter((a) => (form.kind === "bonus" ? a.type === "expense" : a.type === "income")),
    [accounts, form.kind],
  );
  const settleAccounts = useMemo(
    () => (accounts ?? []).filter((a) => a.type === "asset" || a.type === "liability"),
    [accounts],
  );
  const plLabel = form.kind === "bonus" ? "Bonus expense account" : "Recovery / income account";
  const settleLabel = form.kind === "bonus" ? "Pay from (cash / payable)" : "Recovered into (cash / payable)";

  const total = useMemo(() => items.reduce((s, r) => s + (Number(r.amount) || 0), 0), [items]);
  const validRows = items.filter((r) => Number(r.amount) > 0 && (r.staff_user_id || r.staff_name.trim()));

  const resetForm = () => {
    setForm({ label: "", kind: "bonus", reason: "", expense_account_id: "", settle_account_id: "" });
    setItems([emptyRow()]);
    setShow(false);
  };

  const canSubmit = form.label.trim() && form.expense_account_id && form.settle_account_id
    && form.expense_account_id !== form.settle_account_id && validRows.length > 0;

  const submit = () => {
    if (!canSubmit) return;
    create.mutate(
      {
        label: form.label.trim(),
        kind: form.kind,
        reason: form.reason.trim() || null,
        expense_account_id: form.expense_account_id,
        settle_account_id: form.settle_account_id,
        items: validRows.map((r) => ({
          staff_user_id: r.staff_user_id || null,
          staff_name: r.staff_name.trim() || null,
          amount: Number(r.amount),
          note: r.note.trim() || null,
        })),
      },
      { onSuccess: resetForm },
    );
  };

  const setRow = (i: number, patch: Partial<ItemRow>) =>
    setItems((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Bonus/Reduction Pack</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Bonus / Reduction Pack</h1>
          <p className="text-slate-500 text-sm mt-0.5">Apply a batch of bonuses or reductions across staff in one action. Approving posts a single balanced entry to the ledger.</p>
        </div>
        {canWrite && <button onClick={() => { resetForm(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Pack</button>}
      </div>

      <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-5">
        <ShieldCheck size={14} className="mt-0.5 shrink-0" />
        <span>Two-person control: a pack cannot be approved by the person who created it. A <b>bonus</b> posts <span className="font-mono">Dr Expense / Cr Cash</span>; a <b>reduction</b> posts <span className="font-mono">Dr Cash / Cr Income</span>. Approved packs are voided (reversed), never deleted.</span>
      </div>

      <div className="mb-5">
        <select value={kindFilter} onChange={(e) => setKindFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All kinds</option>
          <option value="bonus">Bonus</option>
          <option value="reduction">Reduction</option>
        </select>
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Pay Adjustment Pack</h2><button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="label">Type *</label>
              <div className="flex gap-2">
                <button type="button" onClick={() => setForm({ ...form, kind: "bonus", expense_account_id: "" })} className={cn("flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-semibold", form.kind === "bonus" ? "border-emerald-300 bg-emerald-50 text-emerald-700" : "border-slate-200 text-slate-500 hover:bg-slate-50")}><PlusCircle size={15} /> Bonus</button>
                <button type="button" onClick={() => setForm({ ...form, kind: "reduction", expense_account_id: "" })} className={cn("flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-semibold", form.kind === "reduction" ? "border-amber-300 bg-amber-50 text-amber-700" : "border-slate-200 text-slate-500 hover:bg-slate-50")}><MinusCircle size={15} /> Reduction</button>
              </div>
            </div>
            <div><label className="label">Label *</label><input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} className="input" placeholder={form.kind === "bonus" ? "e.g. December Performance Bonus" : "e.g. Late-arrival penalty"} /></div>
            <div>
              <label className="label">{plLabel} *</label>
              <select value={form.expense_account_id} onChange={(e) => setForm({ ...form, expense_account_id: e.target.value })} className="input">
                <option value="">Select account…</option>
                {plAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}
              </select>
              {plAccounts.length === 0 && <p className="text-[11px] text-amber-600 mt-1">No {form.kind === "bonus" ? "expense" : "income"} accounts yet — add one under Chart of Accounts.</p>}
            </div>
            <div>
              <label className="label">{settleLabel} *</label>
              <select value={form.settle_account_id} onChange={(e) => setForm({ ...form, settle_account_id: e.target.value })} className="input">
                <option value="">Select account…</option>
                {settleAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}
              </select>
            </div>
          </div>

          {/* Line items — grid layout (NOT a table with overflow-hidden, which would
              clip the staff picker's dropdown). Free-text name is the primary field so
              you're never blocked; linking a staff record is an optional enhancement. */}
          <label className="label">Staff lines *</label>
          <div className="hidden md:grid grid-cols-12 gap-2 px-1 pb-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
            <div className="col-span-4">Staff name</div>
            <div className="col-span-3">Link staff (optional)</div>
            <div className="col-span-2">Amount (₦)</div>
            <div className="col-span-2">Note</div>
            <div className="col-span-1" />
          </div>
          <div className="space-y-2 mb-3">
            {items.map((r, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-start">
                <input
                  value={r.staff_name}
                  onChange={(e) => setRow(i, { staff_name: e.target.value, staff_user_id: "" })}
                  className="input col-span-12 md:col-span-4"
                  placeholder="Type a name…"
                />
                <div className="col-span-12 md:col-span-3">
                  <EntityPicker
                    type="staff"
                    value={r.staff_user_id || null}
                    valueLabel={r.staff_user_id ? r.staff_name || null : null}
                    onChange={(id, label) => setRow(i, { staff_user_id: id || "", staff_name: id ? (label || r.staff_name) : r.staff_name })}
                    placeholder="Search staff…"
                  />
                </div>
                <input type="number" min="0" value={r.amount} onChange={(e) => setRow(i, { amount: e.target.value })} className="input col-span-7 md:col-span-2" placeholder="0.00" />
                <input value={r.note} onChange={(e) => setRow(i, { note: e.target.value })} className="input col-span-4 md:col-span-2" placeholder="optional" />
                <div className="col-span-1 flex items-center justify-center pt-2">
                  {items.length > 1 && <button onClick={() => setItems((rows) => rows.filter((_, idx) => idx !== i))} className="text-slate-400 hover:text-red-600" title="Remove line"><Trash2 size={15} /></button>}
                </div>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mb-4">
            <button onClick={() => setItems((rows) => [...rows, emptyRow()])} className="btn-secondary gap-1.5 text-xs"><Plus size={13} /> Add staff line</button>
            <div className="text-sm text-slate-600">Total: <span className="font-bold text-slate-900">{naira(total)}</span></div>
          </div>

          <div><label className="label">Reason / note (optional)</label><input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="input mb-4" placeholder="Context for this pack" /></div>

          <div className="flex justify-end gap-3"><button onClick={resetForm} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!canSubmit || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create draft</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Pack", "Type", "Staff", "Total", "Status", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load packs.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : packs && packs.length > 0 ? (
              packs.map((p: PayAdjustmentPack) => (
                <tr key={p.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{p.label}{p.reason && <span className="block text-[11px] text-slate-400">{p.reason}</span>}<span className="block text-[11px] text-slate-400">{formatDate(p.created_at)}</span></td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", KIND_STYLE[p.kind] || "")}>{p.kind}</span></td>
                  <td className="px-5 py-4 text-sm text-slate-600">{p.items.length} {p.items.length === 1 ? "person" : "people"}</td>
                  <td className="px-5 py-4 text-sm font-semibold text-slate-800">{naira(p.total_amount)}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[p.status] || "")}>{p.status}</span></td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1">
                      {p.status === "draft" && canPost && <button onClick={() => { if (confirm(`Approve & post "${p.label}"? This writes to the ledger.`)) approve.mutate(p.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><CheckCircle2 size={13} /> Approve</button>}
                      {p.status === "approved" && canPost && <button onClick={() => { if (confirm(`Void "${p.label}"? This reverses the ledger entry.`)) voidPack.mutate(p.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Ban size={13} /> Void</button>}
                      {p.status === "draft" && canWrite && <button onClick={() => { if (confirm("Delete this draft pack?")) del.mutate(p.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><Gift size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No bonus or reduction packs yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
