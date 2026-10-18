import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { officeApi } from "@/lib/api";

export const useOfficeSchema = (m: string) => useQuery({ queryKey: ["office", m, "schema"], queryFn: () => officeApi.schema(m), retry: false });
export const useOfficeSummary = (m: string, enabled = true) => useQuery({ queryKey: ["office", m, "summary"], queryFn: () => officeApi.summary(m), enabled });
export const useOfficeRows = (m: string, r: string, q?: string) => useQuery({ queryKey: ["office", m, "rows", r, q ?? ""], queryFn: () => officeApi.list(m, r, q) });

export function useOfficeSave(m: string, r: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: object }) => (id ? officeApi.update(m, r, id, body) : officeApi.create(m, r, body)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["office", m] }),
  });
}
export function useOfficeDelete(m: string, r: string) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: string) => officeApi.remove(m, r, id), onSuccess: () => qc.invalidateQueries({ queryKey: ["office", m] }) });
}
