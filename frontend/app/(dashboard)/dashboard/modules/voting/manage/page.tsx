"use client";

import { useState } from "react";
import {
  useVSessions, useCreateVSession, useDeleteVSession, useOpenVSession, useConductVSession, usePublishVSession,
  useVCategories, useVCandidates, useAddCandidate, useRemoveCandidate, useVResults, type VSession,
} from "@/hooks/useVoting";
import { useAvailableRoles, useStaff } from "@/hooks/useUsers";
import { useSessions } from "@/hooks/usePlatform";
import { cn } from "@/lib/utils";
import { Vote, Plus, Loader2, AlertTriangle, ArrowLeft, Trash2, X, Play, Square, Trophy, Crown } from "lucide-react";

const STATUS_STYLE: Record<string, string> = { draft: "bg-slate-100 text-slate-500 border-slate-200", open: "bg-emerald-50 text-emerald-700 border-emerald-200", conducted: "bg-blue-50 text-blue-700 border-blue-200" };
const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : null);

export default function ManageVotesPage() {
  const [open, setOpen] = useState<VSession | null>(null);
  if (open) return <SessionDetail session={open} onBack={() => setOpen(null)} />;
  return <SessionsList onOpen={setOpen} />;
}

function SessionsList({ onOpen }: { onOpen: (s: VSession) => void }) {
  const { data, isLoading, isError, refetch } = useVSessions();
  const { data: categories } = useVCategories();
  const { data: rolesData } = useAvailableRoles();
  const { data: sessions } = useSessions();
  const create = useCreateVSession();
  const rows = data ?? [];
  const cats: any[] = (categories as any[]) ?? [];
  const roles: any[] = (rolesData?.items as any[]) ?? [];
  const sessionList: any[] = (sessions as any[]) ?? [];

  const [show, setShow] = useState(false);
  const [f, setF] = useState<{ title: string; starts_at: string; ends_at: string; positions: string; candidate_role: string; voter_role: string; session_id: string; instructions: string; category_ids: string[] }>({ title: "", starts_at: "", ends_at: "", positions: "1", candidate_role: "", voter_role: "", session_id: "", instructions: "", category_ids: [] });
  const reset = () => { setF({ title: "", starts_at: "", ends_at: "", positions: "1", candidate_role: "", voter_role: "", session_id: "", instructions: "", category_ids: [] }); setShow(false); };
  const toggleCat = (id: string) => setF((p) => ({ ...p, category_ids: p.category_ids.includes(id) ? p.category_ids.filter((x) => x !== id) : [...p.category_ids, id] }));
  const submit = () => create.mutate({
    title: f.title.trim(), starts_at: f.starts_at ? new Date(f.starts_at).toISOString() : null, ends_at: f.ends_at ? new Date(f.ends_at).toISOString() : null,
    positions: Number(f.positions) || 1, candidate_role: f.candidate_role || null, voter_role: f.voter_role || null, session_id: f.session_id || null,
    instructions: f.instructions || null, category_ids: f.category_ids,
  }, { onSuccess: reset });

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Voting System</span><span>/</span><span className="text-brand-600 font-semibold">Manage Votes</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Vote Manager</h1>
          <p className="text-slate-500 text-sm mt-0.5">Create and run vote sessions.</p>
        </div>
        <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Vote Session</button>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New vote session</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2"><label className="label">Title *</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder="e.g. Best Staff Award — Autumn Term" /></div>
            <div><label className="label">Start date &amp; time</label><input type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} className="input" /></div>
            <div><label className="label">End date &amp; time</label><input type="datetime-local" value={f.ends_at} onChange={(e) => setF({ ...f, ends_at: e.target.value })} className="input" /></div>
            <div><label className="label">Candidate role</label><select value={f.candidate_role} onChange={(e) => setF({ ...f, candidate_role: e.target.value })} className="input"><option value="">Any</option>{roles.map((r) => <option key={r.id} value={r.slug}>{(r.name || r.slug)?.replace(/_/g, " ")}</option>)}</select></div>
            <div><label className="label">Voters role</label><select value={f.voter_role} onChange={(e) => setF({ ...f, voter_role: e.target.value })} className="input"><option value="">Anyone</option>{roles.map((r) => <option key={r.id} value={r.slug}>{(r.name || r.slug)?.replace(/_/g, " ")}</option>)}</select></div>
            <div><label className="label">Positions (winners per category)</label><input type="number" min="1" value={f.positions} onChange={(e) => setF({ ...f, positions: e.target.value })} className="input" /></div>
            <div><label className="label">Session</label><select value={f.session_id} onChange={(e) => setF({ ...f, session_id: e.target.value })} className="input"><option value="">—</option>{sessionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <div className="md:col-span-2">
              <label className="label">Vote categories *</label>
              <div className="flex flex-wrap gap-2">
                {cats.length === 0 ? <p className="text-xs text-slate-400">No categories — add them under Voting Setup.</p> : cats.map((c) => (
                  <button key={c.id} onClick={() => toggleCat(c.id)} className={cn("text-xs font-semibold rounded-lg border px-2.5 py-1 transition", f.category_ids.includes(c.id) ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200 hover:border-brand-300")}>{c.description}</button>
                ))}
              </div>
            </div>
            <div className="md:col-span-2"><label className="label">Instructions</label><textarea value={f.instructions} onChange={(e) => setF({ ...f, instructions: e.target.value })} className="input min-h-[70px]" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!f.title.trim() || f.category_ids.length === 0 || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load vote sessions.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Vote size={34} className="mb-3 opacity-40" /><p className="font-semibold">No vote sessions yet</p></div>
      ) : (
        <div className="space-y-3">
          {rows.map((s) => (
            <button key={s.id} onClick={() => onOpen(s)} className="w-full text-left bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between gap-3 mb-2">
                <h3 className="text-sm font-bold text-slate-900">{s.title}</h3>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={cn("badge capitalize", STATUS_STYLE[s.status] ?? STATUS_STYLE.draft)}>{s.status}</span>
                  {s.result_published && <span className="badge bg-amber-50 text-amber-700 border-amber-200">Published</span>}
                </div>
              </div>
              <p className="text-xs text-slate-500">{s.positions} position{s.positions === 1 ? "" : "s"} · {s.candidate_count} candidate{s.candidate_count === 1 ? "" : "s"} · {s.total_ballots} vote{s.total_ballots === 1 ? "" : "s"}{fmt(s.starts_at) ? ` · ${fmt(s.starts_at)}` : ""}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SessionDetail({ session, onBack }: { session: VSession; onBack: () => void }) {
  const { data: categories } = useVCategories();
  const { data: candidates } = useVCandidates(session.id);
  const { data: staff } = useStaff();
  const { data: results } = useVResults(session.status !== "draft" ? session.id : undefined);
  const addCand = useAddCandidate();
  const delCand = useRemoveCandidate();
  const openS = useOpenVSession();
  const conduct = useConductVSession();
  const publish = usePublishVSession();
  const del = useDeleteVSession();
  const cats: any[] = (categories as any[]) ?? [];
  const sessionCats = cats.filter((c) => session.category_ids.includes(c.id));
  const staffList: any[] = (staff as any[]) ?? [];
  const cands = candidates ?? [];

  const [addFor, setAddFor] = useState<{ category_id: string; user_id: string }>({ category_id: sessionCats[0]?.id ?? "", user_id: "" });

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4"><ArrowLeft size={14} /> Back to sessions</button>
      <div className="flex items-start justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-black text-slate-900">{session.title}</h1>
          <p className="text-sm text-slate-500 mt-1">{session.positions} position{session.positions === 1 ? "" : "s"} · voters: {session.voter_role || "anyone"}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={cn("badge capitalize self-center", STATUS_STYLE[session.status] ?? STATUS_STYLE.draft)}>{session.status}</span>
          {session.status === "draft" && <button onClick={() => openS.mutate(session.id, { onSuccess: onBack })} className="btn-primary gap-1.5 py-1.5 text-sm"><Play size={14} /> Open voting</button>}
          {session.status === "open" && <button onClick={() => conduct.mutate(session.id, { onSuccess: onBack })} className="btn-secondary gap-1.5 py-1.5 text-sm"><Square size={13} /> Close</button>}
          {session.status === "conducted" && !session.result_published && <button onClick={() => publish.mutate(session.id, { onSuccess: onBack })} className="btn-primary gap-1.5 py-1.5 text-sm"><Trophy size={14} /> Publish result</button>}
          <button onClick={() => { if (confirm("Delete this session?")) { del.mutate(session.id); onBack(); } }} className="text-slate-400 hover:text-red-600 p-2"><Trash2 size={15} /></button>
        </div>
      </div>

      {/* Candidates (draft only) */}
      {session.status === "draft" && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex flex-wrap gap-2 items-end">
          <div className="min-w-[160px]"><label className="label">Category</label><select value={addFor.category_id} onChange={(e) => setAddFor({ ...addFor, category_id: e.target.value })} className="input">{sessionCats.map((c) => <option key={c.id} value={c.id}>{c.description}</option>)}</select></div>
          <div className="flex-1 min-w-[180px]"><label className="label">Candidate (staff)</label><select value={addFor.user_id} onChange={(e) => setAddFor({ ...addFor, user_id: e.target.value })} className="input"><option value="">Select…</option>{staffList.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.email}</option>)}</select></div>
          <button onClick={() => addCand.mutate({ sessionId: session.id, data: { category_id: addFor.category_id, user_id: addFor.user_id } }, { onSuccess: () => setAddFor({ ...addFor, user_id: "" }) })} disabled={!addFor.category_id || !addFor.user_id || addCand.isPending} className="btn-primary gap-1.5">{addCand.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Add</button>
        </div>
      )}

      {/* Per-category: candidates (draft) or results (after) */}
      <div className="space-y-4">
        {sessionCats.map((c) => {
          const catResult = results?.categories.find((r) => r.category_id === c.id);
          const list = session.status === "draft" ? cands.filter((x) => x.category_id === c.id) : (catResult?.candidates ?? []);
          const winners = catResult?.winner_ids ?? [];
          return (
            <div key={c.id} className="bg-white rounded-xl border border-slate-200">
              <div className="px-5 py-3 border-b border-slate-50 flex items-center justify-between">
                <p className="text-sm font-bold text-slate-800">{c.description}</p>
                {session.status !== "draft" && <span className="text-xs text-slate-400">{catResult?.total_votes ?? 0} votes</span>}
              </div>
              {list.length === 0 ? (
                <p className="px-5 py-6 text-sm text-slate-400 text-center">No candidates.</p>
              ) : (
                <div className="divide-y divide-slate-50">
                  {list.map((cand) => (
                    <div key={cand.id} className="flex items-center gap-3 px-5 py-2.5">
                      {winners.includes(cand.id) && session.result_published && <Crown size={15} className="text-amber-500 shrink-0" />}
                      <span className="text-sm font-medium text-slate-800 flex-1 truncate">{cand.name || "—"}</span>
                      {session.status !== "draft" ? <span className="text-sm font-bold text-slate-700 tabular-nums">{cand.votes}</span> : (
                        <button onClick={() => delCand.mutate(cand.id)} className="text-slate-400 hover:text-red-600 p-1"><X size={15} /></button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
