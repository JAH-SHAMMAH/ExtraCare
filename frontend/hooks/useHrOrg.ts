"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { hrOrgApi } from "@/lib/api";

export type OrgUnit = {
  id: string; name: string; unit_type: string | null; parent_id: string | null;
  head_user_id: string | null; head_name: string | null; description: string | null;
  position: number; created_at: string; org_id: string;
};

export function useOrgUnits() {
  return useQuery<OrgUnit[]>({ queryKey: ["hr-org-units"], queryFn: () => hrOrgApi.list() });
}

function orgMut<T>(fn: (v: any) => Promise<T>, ok: string) {
  return () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: fn,
      onSuccess: () => { qc.invalidateQueries({ queryKey: ["hr-org-units"] }); if (ok) toast.success(ok); },
      onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed."),
    });
  };
}

export const useCreateOrgUnit = orgMut((d) => hrOrgApi.create(d), "Unit added.");
export const useUpdateOrgUnit = orgMut((v: { id: string; data: object }) => hrOrgApi.update(v.id, v.data), "Saved.");
export const useDeleteOrgUnit = orgMut((id: string) => hrOrgApi.remove(id), "Removed.");
