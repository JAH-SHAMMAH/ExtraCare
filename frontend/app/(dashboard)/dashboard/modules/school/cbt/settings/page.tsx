"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useCBTSettings, useUpdateCBTSettings } from "@/hooks/useSchoolExperience";
import { Settings2, Loader2, ArrowLeft, Save } from "lucide-react";

export default function CBTSetupPage() {
  const { data, isLoading } = useCBTSettings();
  const save = useUpdateCBTSettings();

  const [duration, setDuration] = useState("60");
  const [passPct, setPassPct] = useState("50");
  const [shuffle, setShuffle] = useState(false);
  const [instructions, setInstructions] = useState("");

  useEffect(() => {
    if (data) {
      setDuration(String(data.default_duration_minutes ?? 60));
      setPassPct(String(data.default_pass_percentage ?? 50));
      setShuffle(Boolean(data.shuffle_default));
      setInstructions(data.instructions || "");
    }
  }, [data]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    save.mutate({
      default_duration_minutes: Number(duration),
      default_pass_percentage: Number(passPct),
      shuffle_default: shuffle,
      instructions: instructions.trim() || null,
    });
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <Link href="/dashboard/modules/school/cbt" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> CBT</Link>
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>CBT</span><span>/</span><span className="text-brand-600 font-semibold">Setup</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">CBT Setup</h1>
        <p className="text-slate-500 text-sm mt-0.5">Default values applied when a new exam is created. Each exam can still override them.</p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : (
        <form onSubmit={submit} className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <label className="label">Default duration (minutes)</label>
              <input type="number" min="1" max="600" value={duration} onChange={(e) => setDuration(e.target.value)} className="input" required />
            </div>
            <div>
              <label className="label">Default pass mark (%)</label>
              <input type="number" min="0" max="100" value={passPct} onChange={(e) => setPassPct(e.target.value)} className="input" required />
            </div>
          </div>

          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox" checked={shuffle} onChange={(e) => setShuffle(e.target.checked)} className="w-4 h-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
            <span className="text-sm text-slate-700">Shuffle questions by default</span>
          </label>

          <div>
            <label className="label">Default instructions</label>
            <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={4} className="input resize-none" placeholder="Shown to students before they begin an exam…" />
          </div>

          <div className="flex justify-end pt-1">
            <button type="submit" disabled={save.isPending} className="btn-primary gap-2">
              {save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save defaults
            </button>
          </div>
        </form>
      )}

      <div className="flex items-center gap-2 text-xs text-slate-400 mt-4">
        <Settings2 size={13} /> These defaults pre-fill the exam builder; they don't change existing exams.
      </div>
    </div>
  );
}
