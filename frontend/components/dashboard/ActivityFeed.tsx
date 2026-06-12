"use client";

import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api";
import { timeAgo, SEVERITY_COLORS } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { Skeleton, SkeletonCircle } from "@/components/loading/Skeleton";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import type { ActivityLog } from "@/types";

export function ActivityFeed() {
  const { data: logs = [], isLoading } = useQuery<ActivityLog[]>({
    queryKey: ["analytics", "activity-feed"],
    queryFn: () => analyticsApi.activityFeed(15),
    refetchInterval: 15_000,
  });
  const showSkeleton = useDelayedFlag(isLoading);

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-800">Security & Activity Log</h3>
        <a href="/dashboard/audit" className="text-xs text-brand-600 font-semibold hover:underline">
          View all
        </a>
      </div>

      <div className="divide-y divide-slate-50">
        {showSkeleton
          ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
          : isLoading
          ? null
          : logs.map((log) => <LogRow key={log.id} log={log} />)}

        {!isLoading && !showSkeleton && logs.length === 0 && (
          <div className="px-5 py-8 text-center text-sm text-slate-400">No activity yet.</div>
        )}
      </div>
    </div>
  );
}

function LogRow({ log }: { log: ActivityLog }) {
  const dotColor = SEVERITY_COLORS[log.severity] || "bg-slate-400";
  const action = log.action.replace(".", " ").replace(/_/g, " ");

  return (
    <div className="flex items-start gap-3 px-5 py-3.5 hover:bg-slate-50 transition-colors">
      <div className={cn("mt-1.5 w-2 h-2 rounded-full shrink-0", dotColor)} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-800 capitalize leading-snug">{action}</p>
        {log.resource_label && (
          <p className="text-xs text-slate-500 mt-0.5">
            {log.actor_email && <span className="font-medium">{log.actor_email} · </span>}
            {log.resource_label}
          </p>
        )}
      </div>
      <p className="text-[10px] text-slate-400 uppercase font-medium shrink-0 mt-1">
        {timeAgo(log.created_at)}
      </p>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="flex items-start gap-3 px-5 py-3.5">
      <SkeletonCircle size={8} className="mt-1.5" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-3.5 w-40" />
        <Skeleton className="h-3 w-56" />
      </div>
    </div>
  );
}
