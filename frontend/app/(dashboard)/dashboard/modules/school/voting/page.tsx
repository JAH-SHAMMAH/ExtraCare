"use client";

import { useState } from "react";
import { usePolls, useCreatePoll, useClosePoll, useDeletePoll, useVote } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Gavel, Plus, X, Loader2, Trash2, Lock, Check, AlertTriangle } from "lucide-react";
import type { Poll } from "@/types";

export default function VotingPage() {
  const canWrite = useHasPermission("settings:write");
  const { data, isLoading, isError, refetch } = usePolls();
  const create = useCreatePoll();
  const [show, setShow] = useState(false);
  const [f, setF] = useState({ title: "", description: "", options: ["", ""] });
  const reset = () => { setF({ title: "", description: "", options: ["", ""] }); setShow(false); };
  const polls = data?.items ?? [];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Administration</span><span>/</span><span className="text-brand-600 font-semibold">Polls</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Polls</h1>
          <p className="text-slate-500 text-sm mt-0.5">Polls & elections. One vote per member; results are tallied live from votes.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Poll</button>}
      </div>

      {show && canWrite && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={reset}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">New Poll</h3><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 space-y-4">
              <div><label className="label">Title *</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" /></div>
              <div><label className="label">Description</label><textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input min-h-[60px]" /></div>
              <div>
                <label className="label">Options *</label>
                <div className="space-y-2">
                  {f.options.map((o, i) => (
                    <div key={i} className="flex gap-2">
                      <input value={o} onChange={(e) => { const n = [...f.options]; n[i] = e.target.value; setF({ ...f, options: n }); }} className="input" placeholder={`Option ${i + 1}`} />
                      {f.options.length > 2 && <button onClick={() => setF({ ...f, options: f.options.filter((_, j) => j !== i) })} className="text-slate-400 hover:text-red-600 px-1"><X size={15} /></button>}
                    </div>
                  ))}
                </div>
                <button onClick={() => setF({ ...f, options: [...f.options, ""] })} className="text-xs font-semibold text-brand-600 mt-2">+ Add option</button>
              </div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={() => create.mutate({ title: f.title.trim(), description: f.description || null, options: f.options.map((o) => o.trim()).filter(Boolean) }, { onSuccess: reset })} disabled={!f.title.trim() || f.options.filter((o) => o.trim()).length < 2 || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-40 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load polls.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : polls.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{polls.map((p) => <PollCard key={p.id} poll={p} canWrite={canWrite} />)}</div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Gavel size={36} className="mb-3 opacity-40" /><p className="font-semibold">No polls yet</p></div>
      )}
    </div>
  );
}

function PollCard({ poll, canWrite }: { poll: Poll; canWrite: boolean }) {
  const vote = useVote();
  const close = useClosePoll();
  const del = useDeletePoll();
  const open = poll.status === "open";
  const voted = !!poll.my_vote_option_id;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start justify-between mb-1">
        <h3 className="text-sm font-bold text-slate-900">{poll.title}</h3>
        <span className={cn("badge", open ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500 border-slate-200")}>{open ? "open" : "closed"}</span>
      </div>
      {poll.description && <p className="text-xs text-slate-500 mb-3">{poll.description}</p>}
      <div className="space-y-2 mb-3">
        {poll.options.map((o) => {
          const pct = poll.total_votes ? Math.round((o.votes / poll.total_votes) * 100) : 0;
          const mine = poll.my_vote_option_id === o.id;
          return (
            <button key={o.id} disabled={!open || voted || vote.isPending} onClick={() => vote.mutate({ id: poll.id, data: { option_id: o.id } })}
              className={cn("w-full text-left relative rounded-lg border px-3 py-2 overflow-hidden transition", mine ? "border-brand-400 bg-brand-50/40" : "border-slate-200", open && !voted ? "hover:border-brand-300 cursor-pointer" : "cursor-default")}>
              <div className="absolute inset-y-0 left-0 bg-brand-100/60" style={{ width: `${pct}%` }} />
              <div className="relative flex items-center justify-between text-sm">
                <span className="font-medium text-slate-700 flex items-center gap-1">{mine && <Check size={13} className="text-brand-600" />}{o.label}</span>
                <span className="text-xs text-slate-500">{o.votes} · {pct}%</span>
              </div>
            </button>
          );
        })}
      </div>
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>{poll.total_votes} vote{poll.total_votes === 1 ? "" : "s"}{voted ? " · you voted" : ""}</span>
        {canWrite && (
          <div className="flex items-center gap-2">
            {open && <button onClick={() => close.mutate(poll.id)} className="inline-flex items-center gap-1 font-semibold text-slate-500 hover:text-slate-700"><Lock size={12} /> Close</button>}
            <button onClick={() => { if (confirm("Delete poll?")) del.mutate(poll.id); }} className="text-slate-400 hover:text-red-600"><Trash2 size={13} /></button>
          </div>
        )}
      </div>
    </div>
  );
}
