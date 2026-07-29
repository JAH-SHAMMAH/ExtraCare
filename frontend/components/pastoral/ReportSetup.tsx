"use client";

import { useState } from "react";
import { useRemarkBank, useCreateRemark, useUpdateRemark, useDeleteRemark } from "@/hooks/usePastoral";
import { cn } from "@/lib/utils";
import { Plus, Trash2, Loader2, Power } from "lucide-react";

export function ReportSetup({ canWrite }: { canWrite: boolean }) {
  const { data: rows = [], isLoading } = useRemarkBank();
  const create = useCreateRemark();
  const update = useUpdateRemark();
  const del = useDeleteRemark();
  const [f, setF] = useState({ text: "", category: "" });

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">Reusable remarks for the Pastoral Report. Pick a phrase instead of retyping when writing a boarder&apos;s term remark.</p>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[220px]"><label className="label">Remark</label><input value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} className="input" placeholder="e.g. A dependable and respectful boarder." /></div>
          <div><label className="label">Category</label><input value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} className="input w-36" placeholder="General" /></div>
          <button onClick={() => f.text.trim() && create.mutate({ text: f.text.trim(), category: f.category || null }, { onSuccess: () => setF({ text: "", category: "" }) })} disabled={!f.text.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Remark</button>
        </div>
      )}
      {isLoading ? (
        <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (rows as any[]).length === 0 ? (
        <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No remarks in the bank.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {(rows as any[]).map((r) => (
            <div key={r.id} className="flex items-center justify-between px-5 py-3 gap-3">
              <div className="min-w-0"><p className="text-sm text-slate-800">{r.text}</p>{r.category && <p className="text-xs text-slate-400">{r.category}</p>}</div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={cn("badge", r.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{r.is_active ? "Active" : "Inactive"}</span>
                {canWrite && <>
                  <button onClick={() => update.mutate({ id: r.id, data: { is_active: !r.is_active } })} className="text-slate-400 hover:text-amber-600 p-1"><Power size={15} /></button>
                  <button onClick={() => { if (confirm("Delete this remark?")) del.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
                </>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
