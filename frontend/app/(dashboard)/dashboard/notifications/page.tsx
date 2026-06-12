"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api";
import { cn, timeAgo, SEVERITY_COLORS } from "@/lib/utils";
import { Bell, Check, CheckCheck, Trash2, Filter } from "lucide-react";
import type { ActivityLog } from "@/types";

export default function NotificationsPage() {
  const [filter, setFilter] = useState<string>("all");
  const { data: logs = [], isLoading } = useQuery<ActivityLog[]>({
    queryKey: ["analytics", "activity-feed", "notifications"],
    queryFn: () => analyticsApi.activityFeed(50),
    refetchInterval: 15_000,
  });

  const filtered = filter === "all" ? logs : logs.filter((l) => l.severity === filter);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Core</span><span>/</span>
            <span className="text-brand-600 font-semibold">Notifications</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Notifications</h1>
          <p className="text-slate-500 text-sm mt-0.5">Stay up to date with activity across your organization.</p>
        </div>
        <button className="btn-secondary gap-2 text-sm">
          <CheckCheck size={15} />
          Mark all read
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-2 mb-6">
        {[
          { key: "all", label: "All" },
          { key: "info", label: "Info" },
          { key: "warning", label: "Warnings" },
          { key: "critical", label: "Critical" },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
              filter === key
                ? "bg-brand-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Notification list */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden divide-y divide-slate-50">
        {isLoading ? (
          Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="px-5 py-4 flex items-start gap-3">
              <div className="w-2 h-2 mt-2 rounded-full bg-slate-100 shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-48 bg-slate-100 rounded animate-pulse" />
                <div className="h-3 w-64 bg-slate-100 rounded animate-pulse" />
              </div>
            </div>
          ))
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <Bell size={40} className="mb-3 opacity-40" />
            <p className="font-semibold">No notifications</p>
            <p className="text-sm mt-1">You're all caught up.</p>
          </div>
        ) : (
          filtered.map((log) => {
            const dotColor = SEVERITY_COLORS[log.severity] || "bg-slate-400";
            return (
              <div key={log.id} className="flex items-start gap-3 px-5 py-4 hover:bg-slate-50 transition-colors group">
                <div className={cn("mt-1.5 w-2.5 h-2.5 rounded-full shrink-0", dotColor)} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 capitalize leading-snug">
                    {log.action.replace(".", " ").replace(/_/g, " ")}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {log.actor_email && <span className="font-medium">{log.actor_email} &middot; </span>}
                    {log.resource_label || "System event"}
                  </p>
                  <p className="text-[10px] text-slate-400 mt-1">{timeAgo(log.created_at)}</p>
                </div>
                <button className="p-1.5 rounded-lg text-slate-300 hover:text-slate-600 hover:bg-slate-100 opacity-0 group-hover:opacity-100 transition-all">
                  <Trash2 size={14} />
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
