"use client";

import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/loading/Skeleton";

interface Stat {
  label: string;
  value: number | string;
  delta?: string;
  deltaPositive?: boolean;
  sublabel?: string;
  pulse?: boolean;
  icon: LucideIcon;
  color: string;
}

interface MetricsGridProps {
  stats: Stat[];
  loading?: boolean;
}

export function MetricsGrid({ stats, loading }: MetricsGridProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <StatCard key={stat.label} stat={stat} loading={loading} />
      ))}
    </div>
  );
}

function StatCard({ stat, loading }: { stat: Stat; loading?: boolean }) {
  const Icon = stat.icon;

  return (
    <div className="bg-white rounded-xl border border-slate-200/70 p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center", stat.color)}>
          <Icon size={16} />
        </div>
        {stat.delta && (
          <span className={cn(
            "text-[10px] font-bold px-2 py-0.5 rounded-full",
            stat.deltaPositive ? "text-emerald-700 bg-emerald-50" : "text-red-700 bg-red-50"
          )}>
            {stat.delta}
          </span>
        )}
      </div>

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-7 w-20 rounded-lg" />
          <Skeleton className="h-3 w-24" />
        </div>
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black tracking-tight text-slate-900">{stat.value}</span>
            {stat.pulse && (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
            )}
          </div>
          <p className="text-xs font-bold uppercase tracking-widest text-slate-500 mt-1">{stat.label}</p>
          {stat.sublabel && <p className="text-[10px] text-slate-400 mt-0.5">{stat.sublabel}</p>}
        </>
      )}
    </div>
  );
}
