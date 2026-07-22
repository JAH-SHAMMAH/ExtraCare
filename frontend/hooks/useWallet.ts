"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { walletApi } from "@/lib/api";
import type {
  StudentWallet, WalletDetail, CooperativeMember, CoopMemberDetail, Reconciliation, Paginated,
  WalletSummary, WalletSettings,
} from "@/types";

function inv(qc: ReturnType<typeof useQueryClient>, keys: string[]) {
  keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

// ── Wallets ─────────────────────────────────────────────────────────────────────

export function useWallets() {
  return useQuery<Paginated<StudentWallet>>({ queryKey: ["wallets"], queryFn: () => walletApi.wallets.list() });
}
export function useWallet(id: string | null) {
  return useQuery<WalletDetail>({ queryKey: ["wallets", id], queryFn: () => walletApi.wallets.get(id as string), enabled: !!id });
}
export function useWalletReconciliation() {
  return useQuery<Reconciliation>({ queryKey: ["wallets", "reconciliation"], queryFn: () => walletApi.wallets.reconciliation() });
}
export function useWalletSummary() {
  return useQuery<WalletSummary>({ queryKey: ["wallets", "summary"], queryFn: () => walletApi.wallets.summary() });
}
export function useWalletSettings() {
  return useQuery<WalletSettings>({ queryKey: ["wallets", "settings"], queryFn: () => walletApi.settings.get() });
}
export function useUpdateWalletSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => walletApi.settings.update(data),
    onSuccess: () => { inv(qc, ["wallets"]); toast.success("Wallet settings saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save settings."),
  });
}
export function useCreateWallet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => walletApi.wallets.create(data),
    onSuccess: () => { inv(qc, ["wallets"]); toast.success("Wallet created."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create wallet."),
  });
}
export function useUpdateWallet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => walletApi.wallets.update(id, data),
    onSuccess: () => { inv(qc, ["wallets"]); toast.success("Wallet updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useTopUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => walletApi.wallets.topup(id, data),
    onSuccess: () => { inv(qc, ["wallets", "journal"]); toast.success("Wallet funded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to fund."),
  });
}
export function useWithdraw() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => walletApi.wallets.withdraw(id, data),
    onSuccess: () => { inv(qc, ["wallets", "journal"]); toast.success("Withdrawal recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to withdraw."),
  });
}
export function useSpend() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => walletApi.wallets.spend(id, data),
    onSuccess: () => { inv(qc, ["wallets", "journal"]); toast.success("Spend recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record spend."),
  });
}

// ── Cooperative ───────────────────────────────────────────────────────────────

export function useCoopMembers() {
  return useQuery<Paginated<CooperativeMember>>({ queryKey: ["coop"], queryFn: () => walletApi.cooperative.members() });
}
export function useCoopMember(id: string | null) {
  return useQuery<CoopMemberDetail>({ queryKey: ["coop", id], queryFn: () => walletApi.cooperative.getMember(id as string), enabled: !!id });
}
export function useCoopReconciliation() {
  return useQuery<Reconciliation>({ queryKey: ["coop", "reconciliation"], queryFn: () => walletApi.cooperative.reconciliation() });
}
export function useCreateMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => walletApi.cooperative.createMember(data),
    onSuccess: () => { inv(qc, ["coop"]); toast.success("Member added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add member."),
  });
}
export function useContribute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => walletApi.cooperative.contribute(id, data),
    onSuccess: () => { inv(qc, ["coop", "journal"]); toast.success("Contribution recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record."),
  });
}
export function usePayout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => walletApi.cooperative.payout(id, data),
    onSuccess: () => { inv(qc, ["coop", "journal"]); toast.success("Payout recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record."),
  });
}
