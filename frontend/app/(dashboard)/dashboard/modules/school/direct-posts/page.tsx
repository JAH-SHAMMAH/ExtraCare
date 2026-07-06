"use client";

import { useMemo, useState } from "react";
import { useAccounts, usePostJournal, useJournal } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { BookOpen, Plus, X, Loader2, AlertTriangle, ShieldCheck } from "lucide-react";

type Line = { account_id: string; debit: string; credit: string; description: string };

const emptyLine = (): Line => ({ account_id: "", debit: "", credit: "", description: "" });

export default function DirectPostsPage() {
  const canPost = useHasPermission("payments:post");
  const { data: accounts } = useAccounts({ active_only: true });
  const { data: recent, isLoading, isError, refetch } = useJournal({ page_size: 10 });
  const post = usePostJournal();

  const [entryDate, setEntryDate] = useState("");
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState<Line[]>([emptyLine(), emptyLine()]);

  const totals = useMemo(() => {
    const d = lines.reduce((s, l) => s + (Number(l.debit) || 0), 0);
    const c = lines.reduce((s, l) => s + (Number(l.credit) || 0), 0);
    return { d, c, balanced: d === c && d > 0 };
  }, [lines]);

  const reset = () => { setEntryDate(""); setMemo(""); setLines([emptyLine(), emptyLine()]); };
  const submit = () => {
    const cleaned = lines
      .filter((l) => l.account_id && (Number(l.debit) > 0 || Number(l.credit) > 0))
      .map((l) => ({ account_id: l.account_id, debit: Number(l.debit) || 0, credit: Number(l.credit) || 0, description: l.description || null }));
    if (cleaned.length < 2) return;
    post.mutate(
      { entry_date: entryDate || new Date().toISOString().slice(0, 10), memo: memo || null, lines: cleaned },
      { onSuccess: reset },
    );
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Direct Posts</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Direct Posts</h1>
        <p className="text-slate-500 text-sm mt-0.5">Post a manual, balanced journal entry straight to the general ledger.</p>
      </div>

      {!canPost && (
        <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-5">
          <ShieldCheck size={14} /> Posting to the ledger requires the <b>payments:post</b> capability (accountant/admin). You can draft below, but posting will be rejected.
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div><label className="label">Entry Date</label><input type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} className="input" /></div>
          <div><label className="label">Memo</label><input value={memo} onChange={(e) => setMemo(e.target.value)} className="input" placeholder="Description of this posting" /></div>
        </div>
        <label className="label">Lines (debits must equal credits)</label>
        <div className="space-y-2 mb-3">
          {lines.map((l, i) => (
            <div key={i} className="grid grid-cols-12 gap-2">
              <select value={l.account_id} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, account_id: e.target.value } : x))} className="input col-span-5"><option value="">Account…</option>{(accounts ?? []).map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select>
              <input type="number" value={l.debit} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, debit: e.target.value, credit: "" } : x))} className="input col-span-2" placeholder="Debit" />
              <input type="number" value={l.credit} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, credit: e.target.value, debit: "" } : x))} className="input col-span-2" placeholder="Credit" />
              <input value={l.description} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} className="input col-span-2" placeholder="Note" />
              <button onClick={() => setLines(lines.length > 2 ? lines.filter((_, j) => j !== i) : lines)} className="col-span-1 text-slate-400 hover:text-red-600"><X size={15} /></button>
            </div>
          ))}
        </div>
        <button onClick={() => setLines([...lines, emptyLine()])} className="text-xs font-semibold text-brand-600 hover:text-brand-700 mb-4">+ Add line</button>
        <div className="flex items-center justify-between border-t border-slate-100 pt-4">
          <div className={cn("text-sm font-semibold", totals.balanced ? "text-emerald-600" : "text-slate-500")}>
            Debits {totals.d.toFixed(2)} · Credits {totals.c.toFixed(2)} {totals.balanced ? "· balanced ✓" : "· not balanced"}
          </div>
          <div className="flex gap-3">
            <button onClick={reset} className="btn-secondary">Clear</button>
            <button onClick={submit} disabled={!totals.balanced || post.isPending} className="btn-primary gap-2">{post.isPending && <Loader2 size={15} className="animate-spin" />}Post entry</button>
          </div>
        </div>
      </div>

      <h2 className="text-sm font-bold text-slate-800 mb-3">Recent journal entries</h2>
      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-12 text-center"><AlertTriangle size={26} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load entries.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (recent?.items ?? []).length > 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {recent!.items.map((e: any) => (
            <div key={e.id} className="flex items-center gap-3 px-5 py-3">
              <span className="text-xs text-slate-400 w-24">{e.entry_date ? formatDate(e.entry_date) : "—"}</span>
              <span className="text-sm text-slate-700 flex-1 truncate">{e.memo || <span className="text-slate-400 italic">No memo</span>}</span>
              <span className="badge bg-slate-50 text-slate-500 border-slate-200">{e.source}</span>
              <span className="text-sm font-semibold text-slate-800">{Number(e.total ?? e.lines?.reduce((s: number, l: any) => s + Number(l.debit), 0) ?? 0).toFixed(2)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-14 text-slate-400"><BookOpen size={32} className="mb-3 opacity-40" /><p className="font-semibold">No journal entries yet</p></div>
      )}
    </div>
  );
}
