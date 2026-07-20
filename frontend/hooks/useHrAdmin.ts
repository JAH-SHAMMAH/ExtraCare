"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { hrAdminApi } from "@/lib/api";

export type HrListItem = {
  id: string; list_type: string; name: string; code: string | null;
  description: string | null; sort_order: number; is_active: boolean;
  created_at: string; org_id: string;
};
export type HrListSummary = { list_type: string; label: string; count: number };

function inv(qc: ReturnType<typeof useQueryClient>, listType?: string) {
  qc.invalidateQueries({ queryKey: ["hr-admin-catalog"] });
  qc.invalidateQueries({ queryKey: ["hr-admin-list", listType] });
  if (!listType) qc.invalidateQueries({ queryKey: ["hr-admin-list"] });
}

export function useHrCatalog() {
  return useQuery<HrListSummary[]>({ queryKey: ["hr-admin-catalog"], queryFn: () => hrAdminApi.catalog() });
}

export function useHrList(listType: string) {
  return useQuery<HrListItem[]>({
    queryKey: ["hr-admin-list", listType],
    queryFn: () => hrAdminApi.list(listType),
    enabled: !!listType,
  });
}

export function useCreateHrItem(listType: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (d: object) => hrAdminApi.create(listType, d),
    onSuccess: () => { inv(qc, listType); toast.success("Added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t add."),
  });
}

export function useUpdateHrItem(listType: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; data: object }) => hrAdminApi.update(v.id, v.data),
    onSuccess: () => { inv(qc, listType); toast.success("Saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t save."),
  });
}

export function useDeleteHrItem(listType: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => hrAdminApi.remove(id),
    onSuccess: () => { inv(qc, listType); toast.success("Removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t remove."),
  });
}
