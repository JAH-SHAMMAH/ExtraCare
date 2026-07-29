"use client";

import { useEffect, useState } from "react";
import { useHostels, useRollCall, useMarkRollCall } from "@/hooks/usePastoral";
import { cn } from "@/lib/utils";
import { Loader2, Save, ClipboardCheck } from "lucide-react";

const SESSIONS = ["morning", "afternoon", "evening", "night"];
const STATUSES: [string, string][] = [
  ["present", "bg-emerald-100 text-emerald-700"],
  ["absent", "bg-red-100 text-red-700"],
  ["exeat", "bg-blue-100 text-blue-700"],
  ["sick", "bg-amber-100 text-amber-700"],
];

function todayISO() { return new Date().toISOString().slice(0, 10); }

export function RollCall({ canWrite }: { canWrite: boolean }) {
  const { data: hostelData } = useHostels();
  const hostels = hostelData?.items ?? [];
  const [hostelId, setHostelId] = useState("");
  const [rollDate, setRollDate] = useState(todayISO());
  const [session, setSession] = useState("evening");
  const { data: rows = [], isLoading } = useRollCall({ hostel_id: hostelId, roll_date: rollDate, session });
  const mark = useMarkRollCall();

  const [draft, setDraft] = useState<Record<string, string>>({});
  useEffect(() => {
    const seed: Record<string, string> = {};
    (rows as any[]).forEach((r) => { seed[r.student_id] = r.status || "present"; });
    setDraft(seed);
  }, [rows]);

  const save = () => {
    mark.mutate({
      hostel_id: hostelId, roll_date: rollDate, session,
      marks: (rows as any[]).map((r) => ({ student_id: r.student_id, status: draft[r.student_id] || "present" })),
    });
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
        <div><label className="label">Hostel</label>
          <select value={hostelId} onChange={(e) => setHostelId(e.target.value)} className="input">
            <option value="">— Select —</option>
            {(hostels as any[]).map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
        </div>
        <div><label className="label">Date</label><input type="date" value={rollDate} onChange={(e) => setRollDate(e.target.value)} className="input" /></div>
        <div><label className="label">Session</label><select value={session} onChange={(e) => setSession(e.target.value)} className="input capitalize">{SESSIONS.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
        {canWrite && hostelId && (rows as any[]).length > 0 && (
          <button onClick={save} disabled={mark.isPending} className="btn-primary gap-2 ml-auto">{mark.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save Roll Call</button>
        )}
      </div>

      {!hostelId ? (
        <p className="text-sm text-slate-400 py-8 text-center bg-white rounded-xl border border-slate-200">Select a hostel to take roll call.</p>
      ) : isLoading ? (
        <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (rows as any[]).length === 0 ? (
        <div className="py-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200"><ClipboardCheck size={28} className="mx-auto mb-2 opacity-40" /><p className="text-sm">No boarders in this hostel.</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {(rows as any[]).map((r) => (
            <div key={r.student_id} className="flex items-center justify-between px-5 py-3 gap-3">
              <div className="min-w-0"><p className="text-sm font-semibold text-slate-800 truncate">{r.student_name}</p>{r.room && <p className="text-xs text-slate-400">Room {r.room}</p>}</div>
              <div className="flex gap-1 shrink-0">
                {STATUSES.map(([s, activeCls]) => (
                  <button key={s} disabled={!canWrite}
                    onClick={() => setDraft((p) => ({ ...p, [r.student_id]: s }))}
                    className={cn("text-xs font-semibold rounded-md px-2.5 py-1 capitalize transition",
                      (draft[r.student_id] || "present") === s ? activeCls : "bg-slate-50 text-slate-400 hover:bg-slate-100", !canWrite && "cursor-default")}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
