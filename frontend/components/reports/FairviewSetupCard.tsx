"use client";

import { useState } from "react";
import { platformApi } from "@/lib/api";
import { Loader2, Sparkles } from "lucide-react";

/** Preview-first button that puts the Educare-style cards in place. */
export function FairviewSetupCard() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  const run = async (apply: boolean) => {
    setBusy(true); setError("");
    try { setResult(await platformApi.fairviewSetup(apply)); }
    catch (e: any) { setError(e?.response?.data?.detail || "Could not run the setup."); }
    finally { setBusy(false); }
  };

  const added = result ? Object.values(result.domains ?? {}).reduce((n: number, d: any) => n + (d?.added?.length ?? 0), 0) : 0;
  const cols = result?.columns?.added?.length ?? 0;
  const m = result?.marks;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6" data-testid="fairview-setup">
      <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2"><Sparkles size={15} className="text-brand-600" /> Set up Educare-style report cards</h2>
      <p className="text-xs text-slate-500 mt-1">Adds the skills / nursery goals and the CA 1, CA 2, PRJ, C.E and EXAM columns, then carries the marks already in the portal onto them. Old marks are kept and the old columns are only hidden. Preview first &mdash; nothing changes until you press Apply.</p>
      <div className="flex gap-2 mt-3">
        <button disabled={busy} onClick={() => run(false)} className="btn-secondary gap-2">{busy && <Loader2 size={14} className="animate-spin" />} Preview</button>
        {result && !result.applied && <button disabled={busy} onClick={() => run(true)} className="btn-primary">Apply</button>}
      </div>
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
      {result && (
        <ul className="text-xs text-slate-600 mt-3 space-y-1">
          <li>{result.applied ? "Done." : "Preview (nothing changed yet)."}</li>
          <li>{added} skill / goal rows {result.applied ? "added" : "to add"}; {cols} columns {result.applied ? "added" : "to add"}.</li>
          {m && <li>{m.scores_added} component marks {result.applied ? "carried over" : "to carry over"} from {m.legacy_assessments} old column(s){m.retired ? "; old columns hidden" : ""}.</li>}
          {[...(result.columns?.problems ?? []), ...(m?.problems ?? [])].map((p: string) => <li key={p} className="text-amber-700">{p}</li>)}
        </ul>
      )}
    </div>
  );
}
