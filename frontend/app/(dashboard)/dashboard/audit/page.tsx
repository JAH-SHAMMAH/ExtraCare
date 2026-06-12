"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api";
import { cn, timeAgo, SEVERITY_COLORS } from "@/lib/utils";
import { Shield, Download, Filter } from "lucide-react";
import type { ActivityLog } from "@/types";

export default function AuditLogPage() {
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  // Audit Log reads the audit_logs:read-gated endpoint (org_admin only), not
  // the broad analytics:read activity feed — so teachers/staff can no longer
  // view the audit trail by navigating directly to /dashboard/audit.
  const { data: logs = [], isLoading } = useQuery<ActivityLog[]>({
    queryKey: ["analytics", "audit-log"],
    queryFn: () => analyticsApi.auditLog(100),
    refetchInterval: 15_000,
  });

  const filtered = severityFilter === "all" ? logs : logs.filter((l) => l.severity === severityFilter);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Core</span><span>/</span>
            <span className="text-brand-600 font-semibold">Audit Log</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Audit Log</h1>
          <p className="text-slate-500 text-sm mt-0.5">Complete security and activity trail for your organization.</p>
        </div>
        <button className="btn-secondary gap-2">
          <Download size={15} />
          Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-center gap-3">
        <Filter size={14} className="text-slate-400" />
        {["all", "info", "warning", "critical"].map((sev) => (
          <button
            key={sev}
            onClick={() => setSeverityFilter(sev)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all capitalize",
              severityFilter === sev ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            )}
          >
            {sev}
          </button>
        ))}
        <span className="ml-auto text-xs text-slate-400">{filtered.length} events</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                {["Severity", "Action", "Actor", "Resource", "Time"].map((h) => (
                  <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading
                ? Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 5 }).map((_, j) => (
                      <td key={j} className="px-5 py-4"><div className="h-4 w-24 bg-slate-100 rounded animate-pulse" /></td>
                    ))}
                  </tr>
                ))
                : filtered.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <div className={cn("w-2 h-2 rounded-full", SEVERITY_COLORS[log.severity] || "bg-slate-400")} />
                        <span className="text-xs font-semibold uppercase text-slate-600">{log.severity}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-sm font-medium text-slate-800 capitalize">
                        {log.action.replace(".", " ").replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-xs text-slate-600">{log.actor_email || "System"}</span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-xs text-slate-500">{log.resource_label || "—"}</span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-xs text-slate-400">{timeAgo(log.created_at)}</span>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {!isLoading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <Shield size={40} className="mb-3 opacity-40" />
            <p className="font-semibold">No audit events</p>
            <p className="text-sm mt-1">Activity will appear here as it happens.</p>
          </div>
        )}
      </div>
    </div>
  );
}
