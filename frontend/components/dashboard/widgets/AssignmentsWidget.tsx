"use client";

import { useAssignments } from "@/hooks/useSchoolExperience";
import { WidgetCard, WidgetMetric } from "./WidgetCard";
import { NotebookPen } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { Assignment } from "@/types";

/**
 * Surfaces published assignments. Same component for all personas — only
 * the framing copy differs based on `audience`.
 */
export function AssignmentsWidget({ audience = "teacher" }: { audience?: "admin" | "teacher" | "student" }) {
  // Students/teachers see their own slice via server-side resolution; admins see school-wide.
  const { data, isLoading } = useAssignments({
    status: "published",
    for_me: audience !== "admin",
    page: 1,
    page_size: 5,
  });
  const items = data?.items as Assignment[] | undefined;

  const title = audience === "student" ? "My Assignments" : audience === "teacher" ? "Active Assignments" : "Published Assignments";

  const now = Date.now();
  const upcoming = items?.filter((a) => a.due_date && new Date(a.due_date).getTime() > now).length ?? 0;
  const overdue = items?.filter((a) => a.due_date && new Date(a.due_date).getTime() <= now).length ?? 0;

  return (
    <WidgetCard
      title={title}
      icon={NotebookPen}
      iconClass="bg-indigo-50 text-indigo-600"
      href={audience === "admin" ? "/dashboard/modules/school/eclassroom" : "/dashboard/modules/school/eclassroom?mine=1"}
      viewLabel={audience === "admin" ? "View all" : "View mine"}
      loading={isLoading}
      empty={!items || items.length === 0}
      emptyText="No active assignments."
      tone={overdue > 0 ? "warning" : "default"}
    >
      <div className="grid grid-cols-2 gap-3 mb-3">
        <WidgetMetric label="Upcoming" value={upcoming} />
        <WidgetMetric label="Overdue" value={overdue} tone={overdue > 0 ? "negative" : "neutral"} />
      </div>
      <ul className="space-y-1.5">
        {items?.slice(0, 3).map((a) => (
          <li key={a.id} className="flex items-center justify-between text-xs">
            <span className="text-slate-700 truncate flex-1 mr-2">{a.title}</span>
            <span className="text-slate-400 shrink-0">
              {a.due_date ? formatDate(a.due_date) : "—"}
            </span>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
