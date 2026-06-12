"use client";

import { Building2 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Branded full-screen loader. Used on app entry while Zustand hydrates the
 * auth store and during auth redirects, where we need *something* between
 * "body paints" and "dashboard mounts". Keep this component lightweight —
 * it must render before any app code has run.
 */
export function Splash({
  label = "Loading your portal",
  compact = false,
}: {
  label?: string;
  /** When true, renders inline instead of fixed — useful inside auth cards. */
  compact?: boolean;
}) {
  const container = compact
    ? "flex flex-col items-center justify-center py-12"
    : "fixed inset-0 z-50 flex flex-col items-center justify-center bg-gradient-to-br from-white via-brand-50/40 to-white";

  return (
    <div className={cn(container, "animate-fade-in")} role="status" aria-live="polite">
      <div className="relative mb-5">
        <div className="w-16 h-16 rounded-2xl bg-brand-600 shadow-lg shadow-brand-600/25 flex items-center justify-center">
          <Building2 size={28} className="text-white" />
        </div>
        <span className="absolute -inset-1.5 rounded-[1.25rem] border-2 border-brand-400/40 animate-ping" />
      </div>

      <p className="text-sm font-black tracking-tight text-slate-900">Fairview School Portal</p>
      <p className="text-xs text-slate-500 mt-1">{label}…</p>

      <div className="mt-6 flex items-center gap-1.5" aria-hidden>
        <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-bounce [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-bounce [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-bounce" />
      </div>

      <span className="sr-only">{label}</span>
    </div>
  );
}
