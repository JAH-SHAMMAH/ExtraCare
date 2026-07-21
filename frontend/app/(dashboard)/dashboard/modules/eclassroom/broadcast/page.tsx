"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useEcSchedules, useCreateEcSchedule, useGoLiveEcSchedule, useEndEcBroadcast, type EcSchedule } from "@/hooks/useEclassroom";
import { useSessions } from "@/hooks/usePlatform";
import { useYearGroups } from "@/hooks/useSchool";
import { cn } from "@/lib/utils";
import { Radio, Plus, Loader2, AlertTriangle, Play, Video, Square, X } from "lucide-react";

// The existing WebRTC live room (reused verbatim).
const liveRoom = (sessionId: string) => `/dashboard/modules/school/cbt/live/${sessionId}`;
const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : null);

export default function LiveBroadcastPage() {
  const router = useRouter();
  const { data, isLoading, isError, refetch } = useEcSchedules({ status: "live_new" });
  const { data: sessions } = useSessions();
  const { data: yearGroups } = useYearGroups();
  const create = useCreateEcSchedule();
  const goLive = useGoLiveEcSchedule();
  const end = useEndEcBroadcast();
  const rows = data ?? [];
  const sessionList: any[] = (sessions as any[]) ?? [];
  const ygList: any[] = (yearGroups as any[]) ?? [];

  const [show, setShow] = useState(false);
  const [f, setF] = useState({ title: "", year_group_id: "", session_id: "", scheduled_at: "" });
  const reset = () => { setF({ title: "", year_group_id: "", session_id: "", scheduled_at: "" }); setShow(false); };
  const submit = () => create.mutate(
    { title: f.title.trim(), year_group_id: f.year_group_id || null, session_id: f.session_id || null, scheduled_at: f.scheduled_at ? new Date(f.scheduled_at).toISOString() : null },
    { onSuccess: reset },
  );
  const onGoLive = (id: string) => goLive.mutate(id, { onSuccess: (s: EcSchedule) => { if (s.live_session_id) router.push(liveRoom(s.live_session_id)); } });

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>eClassroom</span><span>/</span><span className="text-brand-600 font-semibold">Live Broadcast</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Live Broadcast</h1>
          <p className="text-slate-500 text-sm mt-0.5">Start a live class for a year group — it opens in the portal’s live room.</p>
        </div>
        <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Create Broadcast</button>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New broadcast</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2"><label className="label">Title *</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder="e.g. Year 9 Live Physics" /></div>
            <div><label className="label">Year group</label><select value={f.year_group_id} onChange={(e) => setF({ ...f, year_group_id: e.target.value })} className="input"><option value="">—</option>{ygList.map((y) => <option key={y.id} value={y.id}>{y.name}</option>)}</select></div>
            <div><label className="label">Session</label><select value={f.session_id} onChange={(e) => setF({ ...f, session_id: e.target.value })} className="input"><option value="">—</option>{sessionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <div><label className="label">Scheduled for</label><input type="datetime-local" value={f.scheduled_at} onChange={(e) => setF({ ...f, scheduled_at: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!f.title.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load broadcasts.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Radio size={34} className="mb-3 opacity-40" /><p className="font-semibold">No broadcasts scheduled</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((s) => {
            const isLive = s.status === "live" && s.live_session_id;
            return (
              <div key={s.id} className="flex items-center gap-3 px-5 py-3.5">
                {isLive && <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse shrink-0" />}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-800 truncate">{s.title}</p>
                  <p className="text-xs text-slate-400 truncate">{[s.year_group_name, s.session_name, fmt(s.scheduled_at)].filter(Boolean).join(" · ") || (isLive ? "Live now" : "Not started")}</p>
                </div>
                {isLive ? (
                  <div className="flex items-center gap-2 shrink-0">
                    <button onClick={() => router.push(liveRoom(s.live_session_id!))} className="btn-primary gap-1.5 py-1.5 text-sm"><Video size={14} /> Join</button>
                    <button onClick={() => { if (confirm("End this broadcast?")) end.mutate(s.id); }} disabled={end.isPending} className="btn-secondary gap-1.5 py-1.5 text-sm"><Square size={13} /> End</button>
                  </div>
                ) : (
                  <button onClick={() => onGoLive(s.id)} disabled={goLive.isPending} className="btn-primary gap-1.5 py-1.5 text-sm shrink-0">{goLive.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Go Live</button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
