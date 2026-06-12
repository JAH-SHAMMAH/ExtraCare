"use client";

import { useWeeklyRemarks } from "@/hooks/useSchoolExperience";
import { WidgetCard } from "./WidgetCard";
import { MessageCircle } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { WeeklyRemark } from "@/types";

/**
 * The remarks API returns `{ items: [...] }`; other/legacy shapes may be a bare
 * array or `{ data: [...] }`, and React Query can hand us null/undefined while
 * loading. Normalize to a real array so the widget never calls array methods on
 * a non-array (this was throwing "remarks.slice is not a function").
 */
function toRemarksArray(data: unknown): WeeklyRemark[] {
  if (Array.isArray(data)) return data as WeeklyRemark[];
  const obj = (data ?? {}) as { items?: unknown; data?: unknown };
  if (Array.isArray(obj.items)) return obj.items as WeeklyRemark[];
  if (Array.isArray(obj.data)) return obj.data as WeeklyRemark[];
  return [];
}

export function RemarksWidget({ audience = "teacher" }: { audience?: "admin" | "teacher" | "student" }) {
  // Students see their own remarks; teachers see remarks they authored. Both
  // resolved server-side via /me/school-context linkage.
  const { data, isLoading } = useWeeklyRemarks({ for_me: audience !== "admin" });
  const remarks = toRemarksArray(data);

  return (
    <WidgetCard
      title={audience === "student" ? "My Weekly Remarks" : "Recent Remarks"}
      icon={MessageCircle}
      iconClass="bg-teal-50 text-teal-600"
      href={audience === "admin" ? "/dashboard/modules/school/remarks" : "/dashboard/modules/school/remarks?mine=1"}
      viewLabel={audience === "admin" ? "View all" : "View mine"}
      loading={isLoading}
      skeleton="list"
      empty={remarks.length === 0}
      emptyText="No remarks this week."
    >
      <ul className="space-y-2">
        {remarks.slice(0, 4).map((r) => (
          <li key={r.id} className="text-xs">
            <p className="text-slate-700 line-clamp-2">{r.remark}</p>
            <p className="text-[10px] text-slate-400 mt-0.5">
              Week of {formatDate(r.week_start)}
            </p>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
