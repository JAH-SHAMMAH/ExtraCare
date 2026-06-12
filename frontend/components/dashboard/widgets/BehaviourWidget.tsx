"use client";

import {
  useBehaviourRecords,
  useBehaviourSchoolSummary,
} from "@/hooks/useSchoolExperience";
import { WidgetCard, WidgetMetric } from "./WidgetCard";
import { Smile, Frown } from "lucide-react";
import type { BehaviourRecord } from "@/types";

/**
 * Admins get the school-wide 30-day aggregate (server-computed). Teachers see
 * the recent records list — kept paginated since they're acting on incidents,
 * not just watching a trend.
 */
export function BehaviourWidget({ audience = "teacher" }: { audience?: "admin" | "teacher" | "student" }) {
  const isAdmin = audience === "admin";
  const { data: summary, isLoading: loadingSummary } = useBehaviourSchoolSummary(30);
  const { data: recordsData, isLoading: loadingRecords } = useBehaviourRecords({
    page: 1,
    page_size: 5,
  });

  const records = recordsData?.items as BehaviourRecord[] | undefined;
  const recent = records?.slice(0, 3) ?? [];

  const positive = isAdmin
    ? (summary?.breakdown?.positive?.count ?? 0)
    : (records?.filter((r) => r.type === "positive").length ?? 0);
  const negative = isAdmin
    ? (summary?.breakdown?.negative?.count ?? 0)
    : (records?.filter((r) => r.type === "negative").length ?? 0);

  const isLoading = isAdmin ? loadingSummary : loadingRecords;

  return (
    <WidgetCard
      title={isAdmin ? "Behaviour (30 days)" : "Behaviour Tracker"}
      icon={Smile}
      iconClass="bg-emerald-50 text-emerald-600"
      href="/dashboard/modules/school/behaviour"
      loading={isLoading}
      empty={isAdmin ? !summary?.total_count : !records || records.length === 0}
      emptyText="No incidents recorded recently."
      tone={negative > positive ? "danger" : "default"}
    >
      <div className="grid grid-cols-2 gap-3 mb-3">
        <WidgetMetric label="Positive" value={positive} tone="positive" />
        <WidgetMetric label="Negative" value={negative} tone={negative > 0 ? "negative" : "neutral"} />
      </div>
      {!isAdmin && (
        <ul className="space-y-1.5">
          {recent.map((r) => (
            <li key={r.id} className="flex items-center gap-2 text-xs">
              {r.type === "positive" ? (
                <Smile size={12} className="text-emerald-600 shrink-0" />
              ) : (
                <Frown size={12} className="text-rose-600 shrink-0" />
              )}
              <span className="text-slate-700 truncate flex-1">{r.description}</span>
              <span className="text-slate-400 shrink-0">{r.points > 0 ? "+" : ""}{r.points}</span>
            </li>
          ))}
        </ul>
      )}
      {isAdmin && summary?.top_categories?.length > 0 && (
        <ul className="space-y-1.5">
          {summary.top_categories.slice(0, 3).map((c: { category: string; count: number }) => (
            <li key={c.category} className="flex items-center justify-between text-xs">
              <span className="text-slate-700 truncate flex-1 mr-2">{c.category}</span>
              <span className="text-slate-400 shrink-0">{c.count}</span>
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}
