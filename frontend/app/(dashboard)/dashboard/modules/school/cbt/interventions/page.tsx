"use client";

import { useState } from "react";
import Link from "next/link";
import { useInterventions, useUpdateIntervention } from "@/hooks/useSchoolExperience";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { LifeBuoy, Loader2, ArrowLeft, CheckCircle2, Clock } from "lucide-react";

const STATUSES = ["all", "open", "in_progress", "resolved"] as const;
const STATUS_STYLE: Record<string, string> = {
  open: "bg-amber-50 text-amber-700 border-amber-200",
  in_progress: "bg-blue-50 text-blue-700 border-blue-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

interface Intervention {
  id: string; student_name: string | null; student_id: string; reason: string;
  note: string | null; status: string; created_at: string | null; resolved_at: string | null;
}

export default function InterventionsPage() {
  const [tab, setTab] = useState<(typeof STATUSES)[number]>("open");
  const { data, isLoading } = useInterventions({ status: tab === "all" ? undefined : tab });
  const canWrite = useHasPermission("school:write");
  const items: Intervention[] = data?.items || [];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <Link href="/dashboard/modules/school/cbt" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> CBT</Link>
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>CBT</span><span>/</span><span className="text-brand-600 font-semibold">Interventions</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Interventions</h1>
        <p className="text-slate-500 text-sm mt-0.5">Students flagged for follow-up after a test, and how each was resolved.</p>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        {STATUSES.map((s) => (
          <button key={s} onClick={() => setTab(s)} className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize", tab === s ? "bg-brand-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50")}>{s.replace("_", " ")}</button>
        ))}
      </div>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <LifeBuoy size={34} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-slate-500">No {tab === "all" ? "" : tab.replace("_", " ")} interventions</p>
          <p className="text-sm mt-1">Flag a student from the Result Manager after a test.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((iv) => <InterventionCard key={iv.id} iv={iv} canWrite={canWrite} />)}
        </div>
      )}
    </div>
  );
}

function InterventionCard({ iv, canWrite }: { iv: Intervention; canWrite: boolean }) {
  const update = useUpdateIntervention();
  const [note, setNote] = useState(iv.note || "");
  const dirty = note !== (iv.note || "");

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <p className="text-sm font-bold text-slate-900">{iv.student_name || iv.student_id}</p>
          <p className="text-xs text-slate-500 mt-0.5">{iv.reason}</p>
        </div>
        <span className={cn("badge capitalize shrink-0", STATUS_STYLE[iv.status] || "bg-slate-50 text-slate-600 border-slate-200")}>{iv.status.replace("_", " ")}</span>
      </div>

      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        readOnly={!canWrite}
        placeholder="Follow-up note — actions taken, plan…"
        className="input min-h-[60px] resize-none text-sm mt-2"
      />

      {canWrite && (
      <div className="flex items-center justify-between mt-3">
        <div className="flex gap-2">
          {iv.status !== "in_progress" && iv.status !== "resolved" && (
            <button onClick={() => update.mutate({ id: iv.id, data: { status: "in_progress" } })} className="text-xs font-semibold text-blue-600 hover:underline inline-flex items-center gap-1"><Clock size={12} />Start</button>
          )}
          {iv.status !== "resolved" ? (
            <button onClick={() => update.mutate({ id: iv.id, data: { status: "resolved", ...(dirty ? { note } : {}) } })} className="text-xs font-semibold text-emerald-600 hover:underline inline-flex items-center gap-1"><CheckCircle2 size={12} />Resolve</button>
          ) : (
            <button onClick={() => update.mutate({ id: iv.id, data: { status: "open" } })} className="text-xs font-semibold text-amber-600 hover:underline">Reopen</button>
          )}
        </div>
        {dirty && (
          <button onClick={() => update.mutate({ id: iv.id, data: { note } })} disabled={update.isPending} className="btn-secondary text-xs py-1 px-3 gap-1">
            {update.isPending && <Loader2 size={12} className="animate-spin" />}Save note
          </button>
        )}
      </div>
      )}
    </div>
  );
}
