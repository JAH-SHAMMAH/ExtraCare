"use client";

import { Activity, AlertTriangle, Loader2, Radio } from "lucide-react";
import { describeConnection, type ConnectionQualityInput } from "@/lib/live/connectionQuality";

// Persistent connection-quality pill shown in the header. Always visible so
// the user has a permanent signal of network health — not just when the
// adaptive loop downgrades. Classroom teachers especially need this so they
// know whether to repeat a question.
export function ConnectionBadge(props: ConnectionQualityInput) {
  const state = describeConnection(props);
  const icon =
    state.level === "connecting" || state.level === "reconnecting" ? (
      <Loader2 className="w-3 h-3 animate-spin" />
    ) : state.tone === "poor" ? (
      <AlertTriangle className="w-3 h-3" />
    ) : state.tone === "fair" ? (
      <Activity className="w-3 h-3" />
    ) : (
      <Radio className="w-3 h-3" />
    );

  const toneClass =
    state.tone === "good"
      ? "bg-emerald-900/40 text-emerald-300 border-emerald-700/50"
      : state.tone === "fair"
      ? "bg-sky-900/40 text-sky-300 border-sky-700/50"
      : state.tone === "poor"
      ? "bg-rose-900/40 text-rose-300 border-rose-700/50"
      : "bg-slate-800/60 text-slate-300 border-slate-700/60";

  return (
    <span
      title={state.description}
      className={`inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide px-2 py-1 rounded-full border ${toneClass}`}
    >
      {icon}
      {state.label}
    </span>
  );
}
