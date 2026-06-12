"use client";

import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api";

export interface ExecutiveOverview {
  as_of: string;
  students: {
    total: number;
    male: number;
    female: number;
    other: number;
  };
  classes: number;
  teachers: number;
  attendance_today: number;
  transport: {
    active_trips: number;
    students_on_board: number;
    issues: number;
    issue_breakdown: {
      skipped: number;
      cancelled: number;
      running_long: number;
    };
    trips_planned: number;
    trips_completed: number;
  };
  sms: {
    campaigns_today: number;
    sent_today: number;
    delivered_today: number;
    failed_today: number;
  };
}

export interface WorkspaceOverview {
  as_of: string;
  workspace: {
    type: string;
    label: string;
    dashboard_type: string;
    modules_enabled: string[];
  };
  cards: Array<{
    label: string;
    value: number | string;
    sub: string | null;
    href: string;
  }>;
  quick_actions: Array<{
    label: string;
    href: string;
    module: string;
  }>;
}

export function useExecutiveOverview(enabled = true) {
  return useQuery<ExecutiveOverview>({
    queryKey: ["dashboard", "overview"],
    queryFn: () => dashboardApi.overview(),
    enabled,
    // 30s refetch matches the demo's perceived "live" cadence — same as
    // the existing analyticsApi.overview hook used by the legacy admin home.
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useWorkspaceOverview(enabled = true) {
  return useQuery<WorkspaceOverview>({
    queryKey: ["dashboard", "workspace-overview"],
    queryFn: () => dashboardApi.workspaceOverview(),
    enabled,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}
