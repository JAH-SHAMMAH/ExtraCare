import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { superSettingsApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

/** What the shell needs to hide switched-off pages for the signed-in user.
 *  Until it loads nothing is hidden, so a slow network never blanks the menu. */
export function useSuperUi() {
  const user = useAuthStore((s) => s.user);
  return useQuery({ queryKey: ["super-ui"], queryFn: () => superSettingsApi.ui(), enabled: !!user, staleTime: 60_000 });
}

/** The on/off switches only (kept for callers that need just those). */
export function useSuperFlags() {
  const q = useSuperUi();
  return { ...q, data: q.data?.flags } as { data: Record<string, boolean> | undefined };
}

export function useSuperSettings(enabled = true) {
  return useQuery({ queryKey: ["super-settings"], queryFn: () => superSettingsApi.read(), enabled });
}

export function useSuperStruct(enabled = true) {
  return useQuery({ queryKey: ["super-struct"], queryFn: () => superSettingsApi.readStruct(), enabled });
}

const refresh = (qc: ReturnType<typeof useQueryClient>) => {
  qc.invalidateQueries({ queryKey: ["super-settings"] });
  qc.invalidateQueries({ queryKey: ["super-struct"] });
  qc.invalidateQueries({ queryKey: ["super-ui"] });
};

export function useSaveSuperSettings() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (values: Record<string, any>) => superSettingsApi.save(values), onSuccess: () => refresh(qc) });
}

export function useSaveSuperStruct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { key: string; value: any }) => superSettingsApi.saveStruct(v.key, v.value),
    onSuccess: () => refresh(qc),
  });
}
