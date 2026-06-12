"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { leaveApi } from "@/lib/api";
import type { LeaveApplication, LeaveAnalytics, LeaveStatus } from "@/types";

type ListParams = { mine?: boolean; status?: LeaveStatus; limit?: number };

export function useLeaveApplications(params?: ListParams) {
  return useQuery<LeaveApplication[]>({
    queryKey: ["leave", "applications", params],
    queryFn: () => leaveApi.applications.list(params),
  });
}

export function useLeaveApplication(id: string | undefined) {
  return useQuery<LeaveApplication>({
    queryKey: ["leave", "applications", id],
    queryFn: () => leaveApi.applications.get(id as string),
    enabled: !!id,
  });
}

export function useCreateLeave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: leaveApi.applications.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leave"] });
      toast.success("Leave application submitted.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to submit application."),
  });
}

export function useApproveLeave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) =>
      leaveApi.applications.approve(id, note ? { decision_note: note } : undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leave"] });
      toast.success("Leave approved.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to approve."),
  });
}

export function useRejectLeave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) =>
      leaveApi.applications.reject(id, note ? { decision_note: note } : undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leave"] });
      toast.success("Leave rejected.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to reject."),
  });
}

export function useLeaveAnalytics() {
  return useQuery<LeaveAnalytics>({
    queryKey: ["leave", "analytics"],
    queryFn: leaveApi.analytics,
  });
}
