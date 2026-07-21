"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { hrPimApi } from "@/lib/api";

export type AccountRow = {
  user_id: string; full_name: string | null; email: string | null; staff_id: string | null;
  job_title: string | null; department: string | null;
  bank_name: string | null; bank_account_name: string | null; bank_account_number: string | null;
};
export type Transfer = {
  id: string; staff_user_id: string; staff_name: string | null; from_department: string | null;
  to_department: string; to_unit: string | null; effective_date: string | null; reason: string | null;
  created_at: string; org_id: string;
};

export function useAccounts(search?: string) {
  return useQuery<AccountRow[]>({ queryKey: ["hr-accounts", search ?? ""], queryFn: () => hrPimApi.accounts(search) });
}

export function useUpdateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { userId: string; data: object }) => hrPimApi.updateAccount(v.userId, v.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hr-accounts"] }); toast.success("Account saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t save."),
  });
}

export function useTransfers(staffUserId?: string) {
  return useQuery<Transfer[]>({ queryKey: ["hr-transfers", staffUserId ?? "all"], queryFn: () => hrPimApi.transfers(staffUserId) });
}

export function useCreateTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (d: object) => hrPimApi.createTransfer(d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr-transfers"] });
      qc.invalidateQueries({ queryKey: ["staff"] });        // department changed
      qc.invalidateQueries({ queryKey: ["hr-accounts"] });
      toast.success("Transfer logged.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t log transfer."),
  });
}
