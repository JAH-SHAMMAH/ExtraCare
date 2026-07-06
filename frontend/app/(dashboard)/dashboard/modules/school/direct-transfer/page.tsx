"use client";

import { useState } from "react";
import { useAccounts, usePostJournal } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { ArrowLeftRight, Loader2, ShieldCheck } from "lucide-react";

export default function DirectTransferPage() {
  const canPost = useHasPermission("payments:post");
  const { data: accounts } = useAccounts({ active_only: true });
  const post = usePostJournal();

  const [form, setForm] = useState({ from_account_id: "", to_account_id: "", amount: "", entry_date: "", memo: "" });
  const set = (k: string, v: string) => setForm({ ...form, [k]: v });
  const valid = form.from_account_id && form.to_account_id && form.from_account_id !== form.to_account_id && Number(form.amount) > 0;

  const submit = () => {
    if (!valid) return;
    const amt = Number(form.amount);
    // A transfer is a balanced 2-line entry: debit the destination, credit the source.
    post.mutate(
      {
        entry_date: form.entry_date || new Date().toISOString().slice(0, 10),
        memo: form.memo || "Direct transfer",
        lines: [
          { account_id: form.to_account_id, debit: amt, credit: 0, description: "Transfer in" },
          { account_id: form.from_account_id, debit: 0, credit: amt, description: "Transfer out" },
        ],
      },
      { onSuccess: () => setForm({ from_account_id: "", to_account_id: "", amount: "", entry_date: "", memo: "" }) },
    );
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Direct Transfer</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Direct Transfer</h1>
        <p className="text-slate-500 text-sm mt-0.5">Move funds between two ledger accounts (posts a balanced journal entry).</p>
      </div>

      {!canPost && (
        <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-5">
          <ShieldCheck size={14} /> Transfers post to the ledger and require <b>payments:post</b> (accountant/admin).
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div>
          <label className="label">From account *</label>
          <select value={form.from_account_id} onChange={(e) => set("from_account_id", e.target.value)} className="input"><option value="">Select source…</option>{(accounts ?? []).map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select>
        </div>
        <div className="flex justify-center text-slate-300"><ArrowLeftRight size={18} /></div>
        <div>
          <label className="label">To account *</label>
          <select value={form.to_account_id} onChange={(e) => set("to_account_id", e.target.value)} className="input"><option value="">Select destination…</option>{(accounts ?? []).filter((a) => a.id !== form.from_account_id).map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div><label className="label">Amount *</label><input type="number" value={form.amount} onChange={(e) => set("amount", e.target.value)} className="input" placeholder="0.00" /></div>
          <div><label className="label">Date</label><input type="date" value={form.entry_date} onChange={(e) => set("entry_date", e.target.value)} className="input" /></div>
        </div>
        <div><label className="label">Memo</label><input value={form.memo} onChange={(e) => set("memo", e.target.value)} className="input" placeholder="Reason for transfer" /></div>
        <div className="flex justify-end">
          <button onClick={submit} disabled={!valid || post.isPending} className="btn-primary gap-2">{post.isPending ? <Loader2 size={15} className="animate-spin" /> : <ArrowLeftRight size={15} />}Post transfer</button>
        </div>
      </div>
    </div>
  );
}
