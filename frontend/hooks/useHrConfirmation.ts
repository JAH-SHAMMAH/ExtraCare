"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { hrConfirmationApi } from "@/lib/api";

export type Confirmation = {
  id: string; staff_user_id: string; staff_name: string | null; employment_status: string | null;
  probation_start: string | null; due_date: string | null; status: string;
  recommendation: string | null; decided_at: string | null; notes: string | null;
  created_at: string; org_id: string;
};

export function useConfirmations(status?: string) {
  return useQuery<Confirmation[]>({ queryKey: ["hr-confirmations", status ?? "all"], queryFn: () => hrConfirmationApi.list(status) });
}

function inv(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["hr-confirmations"] });
  qc.invalidateQueries({ queryKey: ["hr-accounts"] });   // employment_status may have changed
}

export function useStartConfirmation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (d: object) => hrConfirmationApi.start(d),
    onSuccess: () => { inv(qc); toast.success("Confirmation started."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t start."),
  });
}

export function useDecideConfirmation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; data: object }) => hrConfirmationApi.decide(v.id, v.data),
    onSuccess: (_d, v: any) => { inv(qc); toast.success(v?.data?.decision === "decline" ? "Declined." : "Staff confirmed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t record decision."),
  });
}

export function useCancelConfirmation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => hrConfirmationApi.cancel(id),
    onSuccess: () => { inv(qc); toast.success("Cancelled."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t cancel."),
  });
}
