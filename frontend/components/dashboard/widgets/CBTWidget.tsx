"use client";

import { useCBTExams } from "@/hooks/useSchoolExperience";
import { WidgetCard, WidgetMetric } from "./WidgetCard";
import { MonitorCheck } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { CBTExam } from "@/types";

export function CBTWidget({ audience = "teacher" }: { audience?: "admin" | "teacher" | "student" }) {
  const { data, isLoading } = useCBTExams({
    for_me: audience !== "admin",
    page: 1,
    page_size: 5,
  });
  const items = data?.items as (CBTExam & { is_live?: boolean })[] | undefined;
  // is_live is computed server-side (now ∈ [start_time, end_time] AND status open).
  const liveNow = items?.filter((e) => e.is_live).length ?? 0;
  const upcoming = items?.filter((e) => !e.is_live && e.status !== "closed").length ?? 0;

  return (
    <WidgetCard
      title={audience === "student" ? "My Exams" : "CBT Exams"}
      icon={MonitorCheck}
      iconClass="bg-sky-50 text-sky-600"
      href={audience === "admin" ? "/dashboard/modules/school/cbt" : "/dashboard/modules/school/cbt?mine=1"}
      viewLabel={audience === "admin" ? "View all" : "View mine"}
      loading={isLoading}
      empty={!items || items.length === 0}
      emptyText="No exams scheduled."
      tone={liveNow > 0 ? "warning" : "default"}
    >
      <div className="grid grid-cols-2 gap-3 mb-3">
        <WidgetMetric label="Live Now" value={liveNow} tone={liveNow > 0 ? "positive" : "neutral"} />
        <WidgetMetric label="Upcoming" value={upcoming} />
      </div>
      <ul className="space-y-1.5">
        {items?.slice(0, 3).map((e) => (
          <li key={e.id} className="flex items-center justify-between text-xs">
            <span className="text-slate-700 truncate flex-1 mr-2">{e.title}</span>
            <span className="text-slate-400 shrink-0">
              {e.start_time ? formatDate(e.start_time) : `${e.duration_minutes}m`}
            </span>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
