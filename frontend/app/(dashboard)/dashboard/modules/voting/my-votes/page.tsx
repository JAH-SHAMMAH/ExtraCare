"use client";

import { useState } from "react";
import { useOpenVSessions, useBallot, useCastVote, type VSession } from "@/hooks/useVoting";
import { cn } from "@/lib/utils";
import { Vote, Loader2, AlertTriangle, ArrowLeft, CheckCircle2, Circle, Trophy } from "lucide-react";

export default function MyVotesPage() {
  const [open, setOpen] = useState<VSession | null>(null);
  if (open) return <Ballot session={open} onBack={() => setOpen(null)} />;
  return <OpenList onOpen={setOpen} />;
}

function OpenList({ onOpen }: { onOpen: (s: VSession) => void }) {
  const { data, isLoading, isError, refetch } = useOpenVSessions();
  const rows = data ?? [];
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Voting System</span><span>/</span><span className="text-brand-600 font-semibold">My Votes</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Votes</h1>
        <p className="text-slate-500 text-sm mt-0.5">Cast your vote in open sessions you’re eligible for.</p>
      </div>
      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Vote size={34} className="mb-3 opacity-40" /><p className="font-semibold">No open votes right now</p></div>
      ) : (
        <div className="space-y-3">
          {rows.map((s) => (
            <button key={s.id} onClick={() => onOpen(s)} className="w-full text-left bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow flex items-center justify-between">
              <div><h3 className="text-sm font-bold text-slate-900">{s.title}</h3><p className="text-xs text-slate-500 mt-0.5">{s.category_ids.length} categor{s.category_ids.length === 1 ? "y" : "ies"} to vote</p></div>
              <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">Open</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Ballot({ session, onBack }: { session: VSession; onBack: () => void }) {
  const { data, isLoading } = useBallot(session.id);
  const cast = useCastVote();
  const cats = data?.categories ?? [];
  const mine = data?.my_votes ?? {};

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4"><ArrowLeft size={14} /> Back</button>
      <h1 className="text-2xl font-black text-slate-900 mb-1">{session.title}</h1>
      {data?.instructions && <p className="text-sm text-slate-500 mb-6">{data.instructions}</p>}

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-32 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : (
        <div className="space-y-4">
          {cats.map((c) => {
            const votedCand = mine[c.category_id];
            return (
              <div key={c.category_id} className="bg-white rounded-xl border border-slate-200">
                <div className="px-5 py-3 border-b border-slate-50 flex items-center justify-between">
                  <p className="text-sm font-bold text-slate-800">{c.description}</p>
                  {votedCand && <span className="text-xs font-semibold text-emerald-600 inline-flex items-center gap-1"><CheckCircle2 size={13} /> Voted</span>}
                </div>
                <div className="divide-y divide-slate-50">
                  {c.candidates.length === 0 ? <p className="px-5 py-6 text-sm text-slate-400 text-center">No candidates.</p> : c.candidates.map((cand) => {
                    const chosen = votedCand === cand.id;
                    return (
                      <button
                        key={cand.id}
                        disabled={!!votedCand || cast.isPending}
                        onClick={() => cast.mutate({ sessionId: session.id, data: { category_id: c.category_id, candidate_id: cand.id } })}
                        className={cn("w-full flex items-center gap-3 px-5 py-3 text-left transition-colors", chosen ? "bg-emerald-50/50" : votedCand ? "opacity-50 cursor-default" : "hover:bg-slate-50")}
                      >
                        {chosen ? <Trophy size={16} className="text-emerald-500 shrink-0" /> : <Circle size={16} className="text-slate-300 shrink-0" />}
                        <span className={cn("text-sm font-medium", chosen ? "text-emerald-800" : "text-slate-700")}>{cand.name || "—"}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
