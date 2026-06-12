"use client";

import { useFeedbackList } from "@/hooks/useSchoolExperience";
import { WidgetCard, WidgetMetric } from "./WidgetCard";
import { MessageSquare } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { FeedbackItem } from "@/types";

export function FeedbackWidget({ audience = "admin" }: { audience?: "admin" | "teacher" | "student" }) {
  // Admins/teachers see school-wide queue; students see their own only.
  const mine = audience === "student";
  const { data, isLoading } = useFeedbackList({ mine: mine || undefined, page: 1, page_size: 10 });
  const items = data?.items as FeedbackItem[] | undefined;

  const open = items?.filter((f) => !f.is_resolved).length ?? 0;
  const resolved = items?.filter((f) => f.is_resolved).length ?? 0;

  return (
    <WidgetCard
      title={mine ? "My Feedback" : "Feedback Queue"}
      icon={MessageSquare}
      iconClass="bg-amber-50 text-amber-600"
      href={mine ? "/dashboard/modules/school/feedback?mine=1" : "/dashboard/modules/school/feedback"}
      viewLabel={mine ? "View mine" : "View all"}
      loading={isLoading}
      empty={!items || items.length === 0}
      emptyText="No feedback items."
      tone={!mine && open > 5 ? "warning" : "default"}
    >
      <div className="grid grid-cols-2 gap-3 mb-3">
        <WidgetMetric label="Open" value={open} tone={open > 0 ? "negative" : "neutral"} />
        <WidgetMetric label="Resolved" value={resolved} tone="positive" />
      </div>
      <ul className="space-y-1.5">
        {items?.slice(0, 3).map((f) => (
          <li key={f.id} className="flex items-center justify-between text-xs">
            <span className="text-slate-700 truncate flex-1 mr-2">{f.subject}</span>
            <span className="text-slate-400 shrink-0">{formatDate(f.created_at)}</span>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
