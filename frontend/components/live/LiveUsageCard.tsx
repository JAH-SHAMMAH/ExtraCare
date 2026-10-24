"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, HardDrive, Radio, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

// Usage events that the live router emits. Keep in sync with
// backend/app/routers/live.py track_usage calls.
const LIVE_EVENTS = {
  sessions: "live.session_started",
  minutes: "live.stream_minutes",
  mb: "live.recording_mb",
} as const;

type UsageSeriesResponse = {
  series: { key: string; count: number }[];
  total: number;
};

async function fetchLiveUsage(orgId: string): Promise<Record<string, number>> {
  const { data } = await api.get<UsageSeriesResponse>(
    `/organizations/${orgId}/usage`,
    { params: { days: 30, group_by: "event" } }
  );
  const map: Record<string, number> = {};
  for (const row of data.series || []) {
    if (row.key.startsWith("live.")) map[row.key] = row.count;
  }
  return map;
}

function formatHours(minutes: number): string {
  if (minutes <= 0) return "0 min";
  if (minutes < 60) return `${minutes} min`;
  const hours = minutes / 60;
  return hours >= 10 ? `${Math.round(hours)} hr` : `${hours.toFixed(1)} hr`;
}

function formatStorage(mb: number): string {
  if (mb <= 0) return "0 MB";
  if (mb < 1024) return `${mb} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

export function LiveUsageCard() {
  const org = useAuthStore((s) => s.org);
  const { data, isLoading } = useQuery({
    queryKey: ["live", "usage", org?.id],
    queryFn: () => fetchLiveUsage(org!.id),
    enabled: !!org?.id,
    staleTime: 60_000,
  });

  if (!org) return null;

  const sessions = data?.[LIVE_EVENTS.sessions] ?? 0;
  const minutes = data?.[LIVE_EVENTS.minutes] ?? 0;
  const mb = data?.[LIVE_EVENTS.mb] ?? 0;
  const quotaMb: number | null = null; // no plans: recording storage is not capped
  const pct = quotaMb && quotaMb > 0 ? Math.min(100, (mb / quotaMb) * 100) : 0;
  const nearCap = quotaMb !== null && pct >= 80;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <header className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold text-slate-700 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-brand-500" />
            Live usage — last 30 days
          </h2>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Rolling 30-day window. Counts reset each month for analytics.
          </p>
        </div>
      </header>

      <div className="grid grid-cols-3 gap-3">
        <Metric
          icon={<Radio className="w-4 h-4 text-rose-500" />}
          label="Sessions"
          value={isLoading ? "…" : String(sessions)}
        />
        <Metric
          icon={<Clock className="w-4 h-4 text-amber-500" />}
          label="Hours streamed"
          value={isLoading ? "…" : formatHours(minutes)}
        />
        <Metric
          icon={<HardDrive className="w-4 h-4 text-sky-500" />}
          label="Recording storage"
          value={isLoading ? "…" : formatStorage(mb)}
          sub={
            quotaMb === null
              ? "Unlimited"
              : quotaMb > 0
              ? `of ${formatStorage(quotaMb)}`
              : "Used"
          }
        />
      </div>

      {quotaMb !== null && quotaMb > 0 && (
        <div className="mt-4">
          <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
            <div
              className={`h-full transition-all ${
                nearCap ? "bg-rose-500" : "bg-brand-500"
              }`}
              style={{ width: `${pct}%` }}
            />
          </div>
          {nearCap && (
            <p className="text-[11px] text-rose-600 mt-2">
              You're using {pct.toFixed(0)}% of your recording storage.{" "}Please contact your administrator to free up space.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function Metric({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-lg bg-slate-50 border border-slate-100 p-3">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-lg font-black text-slate-900">{value}</div>
      {sub && <div className="text-[11px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}
