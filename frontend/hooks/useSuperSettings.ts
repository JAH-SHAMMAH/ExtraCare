import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { superSettingsApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

/** The on/off switches, readable by every signed-in user (drives menu + page hiding).
 *  Until it loads, nothing is hidden, so a slow network never blanks the menu. */
export function useSuperFlags() {
  const user = useAuthStore((s) => s.user);
  return useQuery<Record<string, boolean>>({
    queryKey: ["super-flags"], queryFn: () => superSettingsApi.flags(),
    enabled: !!user, staleTime: 60_000,
  });
}

export function useSuperSettings(enabled = true) {
  return useQuery({ queryKey: ["super-settings"], queryFn: () => superSettingsApi.read(), enabled });
}

export function useSaveSuperSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (values: Record<string, any>) => superSettingsApi.save(values),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["super-settings"] }); qc.invalidateQueries({ queryKey: ["super-flags"] }); },
  });
}
