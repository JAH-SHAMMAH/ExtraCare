"use client";

import { useState, useEffect } from "react";
import { useEcSettings, useUpdateEcSettings } from "@/hooks/useEclassroom";
import { cn } from "@/lib/utils";
import { MonitorPlay, Loader2, AlertTriangle } from "lucide-react";

const TOGGLES: { key: "can_teacher_publish" | "automatic_approval" | "learning_program_enabled"; label: string; hint: string }[] = [
  { key: "can_teacher_publish", label: "Teachers can publish", hint: "Let teachers publish eClassroom content without an admin." },
  { key: "automatic_approval", label: "Automatic approval", hint: "Published content goes live immediately, no approval step." },
  { key: "learning_program_enabled", label: "Learning programs", hint: "Enable the Programs (CBT-linked learning program) feature." },
];

export default function EcSetupPage() {
  const { data, isLoading, isError, refetch } = useEcSettings();
  const save = useUpdateEcSettings();
  const [f, setF] = useState({ can_teacher_publish: true, automatic_approval: false, learning_program_enabled: false });
  useEffect(() => { if (data) setF(data); }, [data]);

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>eClassroom</span><span>/</span><span className="text-brand-600 font-semibold">Setup</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">eClassroom Setup</h1>
        <p className="text-slate-500 text-sm mt-0.5">How content is published and approved across your eClassrooms.</p>
      </div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load setup.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {TOGGLES.map((t) => (
            <div key={t.key} className="flex items-center justify-between gap-4 px-5 py-4">
              <div><p className="text-sm font-semibold text-slate-800">{t.label}</p><p className="text-xs text-slate-400 mt-0.5">{t.hint}</p></div>
              <button
                onClick={() => setF((prev) => ({ ...prev, [t.key]: !prev[t.key] }))}
                className={cn("relative w-12 h-6 rounded-full transition-colors shrink-0", f[t.key] ? "bg-brand-600" : "bg-slate-300")}
                aria-pressed={f[t.key]}
              >
                <span className={cn("absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform", f[t.key] && "translate-x-6")} />
              </button>
            </div>
          ))}
          <div className="flex justify-end px-5 py-4">
            <button onClick={() => save.mutate(f)} disabled={save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save Settings</button>
          </div>
        </div>
      )}
    </div>
  );
}
