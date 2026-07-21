"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { hrDocumentsApi } from "@/lib/api";

export type HrDocument = {
  id: string; title: string; category: string | null; description: string | null;
  file_url: string; filename: string | null; created_at: string; org_id: string;
};

export function useHrDocuments(category?: string) {
  return useQuery<HrDocument[]>({ queryKey: ["hr-documents", category ?? "all"], queryFn: () => hrDocumentsApi.list(category) });
}

function docMut<T>(fn: (v: any) => Promise<T>, ok: string) {
  return () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: fn,
      onSuccess: () => { qc.invalidateQueries({ queryKey: ["hr-documents"] }); if (ok) toast.success(ok); },
      onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed."),
    });
  };
}

export const useCreateHrDocument = docMut((d) => hrDocumentsApi.create(d), "Document added.");
export const useUpdateHrDocument = docMut((v: { id: string; data: object }) => hrDocumentsApi.update(v.id, v.data), "Saved.");
export const useDeleteHrDocument = docMut((id: string) => hrDocumentsApi.remove(id), "Removed.");
