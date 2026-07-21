"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { leaveConfigApi } from "@/lib/api";

export type LeavePolicy = { leave_type: string; label: string; default_days: number; requires_approval: boolean; is_active: boolean };
export type Entitlement = { leave_type: string; label: string; allocated: number; used: number; remaining: number };

export function useLeavePolicies() {
  return useQuery<LeavePolicy[]>({ queryKey: ["leave-policies"], queryFn: () => leaveConfigApi.policies() });
}

export function useUpdateLeavePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { leaveType: string; data: object }) => leaveConfigApi.updatePolicy(v.leaveType, v.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["leave-policies"] }); qc.invalidateQueries({ queryKey: ["leave-entitlements"] }); toast.success("Saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t save."),
  });
}

export function useEntitlements(userId?: string) {
  return useQuery<Entitlement[]>({ queryKey: ["leave-entitlements", userId ?? "me"], queryFn: () => leaveConfigApi.entitlements(userId) });
}

export function useAssignLeave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (d: object) => leaveConfigApi.assign(d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leave-entitlements"] });
      qc.invalidateQueries({ queryKey: ["leave"] });
      toast.success("Leave assigned.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t assign."),
  });
}
