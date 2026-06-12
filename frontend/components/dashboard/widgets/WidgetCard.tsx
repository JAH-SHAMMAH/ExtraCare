"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

export type WidgetSkeleton = "metrics" | "list" | "grid";

export interface WidgetCardProps {
  title: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  iconClass?: string;
  href?: string;
  /** Label for the top-right link (defaults to "View all"). Persona-aware callers can override, e.g. "View mine". */
  viewLabel?: string;
  loading?: boolean;
  empty?: boolean;
  emptyText?: string;
  children?: React.ReactNode;
  /** Shape of the loading placeholder. `metrics` = two number tiles + 3 rows (default). */
  skeleton?: WidgetSkeleton;
  /** Optional tint for the entire card border to signal urgency. */
  tone?: "default" | "warning" | "danger";
}

const TONE: Record<NonNullable<WidgetCardProps["tone"]>, string> = {
  default: "border-slate-200",
  warning: "border-amber-200 bg-amber-50/30",
  danger: "border-rose-200 bg-rose-50/30",
};

export function WidgetCard({
  title,
  icon: Icon,
  iconClass = "bg-brand-50 text-brand-600",
  href,
  viewLabel = "View all",
  loading,
  empty,
  emptyText = "Nothing to show yet.",
  tone = "default",
  skeleton = "metrics",
  children,
}: WidgetCardProps) {
  return (
    <div className={cn("bg-white rounded-xl border p-5 flex flex-col", TONE[tone])}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", iconClass)}>
            <Icon size={15} />
          </div>
          <h3 className="text-sm font-bold text-slate-800">{title}</h3>
        </div>
        {href && !loading && (
          <Link
            href={href}
            className="text-[11px] font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-0.5"
            aria-label={`${viewLabel} for ${title}`}
          >
            {viewLabel} <ArrowRight size={11} />
          </Link>
        )}
      </div>

      <div className="flex-1 min-h-[64px]">
        {loading ? (
          <WidgetSkeleton variant={skeleton} />
        ) : empty ? (
          <p className="text-xs text-slate-400 text-center py-6">{emptyText}</p>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

/**
 * Shape-matched placeholders. Kept deliberately small (single pulse, no
 * shimmer) so three loading widgets side-by-side don't turn the dashboard
 * into a strobe.
 */
function WidgetSkeleton({ variant }: { variant: WidgetSkeleton }) {
  if (variant === "grid") {
    return (
      <div className="grid grid-cols-3 gap-1.5 animate-pulse">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="aspect-square rounded-lg bg-slate-100" />
        ))}
      </div>
    );
  }
  if (variant === "list") {
    return (
      <ul className="space-y-2 animate-pulse">
        {Array.from({ length: 4 }).map((_, i) => (
          <li key={i} className="h-4 rounded bg-slate-100" style={{ width: `${90 - i * 12}%` }} />
        ))}
      </ul>
    );
  }
  // metrics: two number tiles + 3 list rows
  return (
    <div className="animate-pulse">
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <div className="h-2 w-12 rounded bg-slate-100 mb-2" />
          <div className="h-6 w-16 rounded bg-slate-100" />
        </div>
        <div>
          <div className="h-2 w-12 rounded bg-slate-100 mb-2" />
          <div className="h-6 w-16 rounded bg-slate-100" />
        </div>
      </div>
      <ul className="space-y-1.5">
        {Array.from({ length: 3 }).map((_, i) => (
          <li key={i} className="h-3 rounded bg-slate-100" style={{ width: `${95 - i * 10}%` }} />
        ))}
      </ul>
    </div>
  );
}

export function WidgetMetric({
  label,
  value,
  delta,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  delta?: string;
  tone?: "neutral" | "positive" | "negative";
}) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
      <div className="flex items-baseline gap-2">
        <p className="text-2xl font-black text-slate-900">{value}</p>
        {delta && (
          <span className={cn(
            "text-[11px] font-semibold",
            tone === "positive" && "text-emerald-600",
            tone === "negative" && "text-rose-600",
            tone === "neutral" && "text-slate-500",
          )}>
            {delta}
          </span>
        )}
      </div>
    </div>
  );
}
