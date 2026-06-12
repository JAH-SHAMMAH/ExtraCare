"use client";

import { useClubs } from "@/hooks/useSchoolExperience";
import { WidgetCard, WidgetMetric } from "./WidgetCard";
import { Users2 } from "lucide-react";
import type { Club } from "@/types";

export function ClubsWidget() {
  const { data, isLoading } = useClubs({ page: 1, page_size: 8 });
  const clubs = data?.items as Club[] | undefined;

  const active = clubs?.filter((c) => c.is_active).length ?? 0;
  const totalMembers = clubs?.reduce((sum, c) => sum + (c.member_count ?? 0), 0) ?? 0;

  return (
    <WidgetCard
      title="Clubs &amp; Activities"
      icon={Users2}
      iconClass="bg-violet-50 text-violet-600"
      href="/dashboard/modules/school/clubs"
      loading={isLoading}
      empty={!clubs || clubs.length === 0}
      emptyText="No clubs yet."
    >
      <div className="grid grid-cols-2 gap-3 mb-3">
        <WidgetMetric label="Active" value={active} />
        <WidgetMetric label="Members" value={totalMembers} />
      </div>
      <ul className="space-y-1.5">
        {clubs?.slice(0, 3).map((c) => (
          <li key={c.id} className="flex items-center justify-between text-xs">
            <span className="text-slate-700 truncate flex-1 mr-2">{c.name}</span>
            <span className="text-slate-400 shrink-0">{c.member_count ?? 0} members</span>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
