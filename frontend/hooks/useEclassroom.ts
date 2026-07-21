"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { eclassroomApi } from "@/lib/api";

export type EcSettings = { can_teacher_publish: boolean; automatic_approval: boolean; learning_program_enabled: boolean };
export type EcProgram = { id: string; name: string; description: string | null; cbt_type: string; section_id: string | null; section_name: string | null; session_id: string | null; session_name: string | null; is_active: boolean; created_at: string; org_id: string };
export type EcSchedule = { id: string; title: string; description: string | null; section_id: string | null; section_name: string | null; session_id: string | null; session_name: string | null; year_group_id: string | null; year_group_name: string | null; scheduled_at: string | null; status: string; live_session_id: string | null; created_at: string; org_id: string };

// ── Setup ─────────────────────────────────────────────────────────────────────
export function useEcSettings() {
  return useQuery<EcSettings>({ queryKey: ["ec-settings"], queryFn: () => eclassroomApi.settings() });
}
export function useUpdateEcSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (d: object) => eclassroomApi.updateSettings(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ec-settings"] }); toast.success("Settings saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t save."),
  });
}

// ── Programs ──────────────────────────────────────────────────────────────────
export function useEcPrograms(params?: { session_id?: string; section_id?: string; cbt_type?: string }) {
  return useQuery<EcProgram[]>({ queryKey: ["ec-programs", params], queryFn: () => eclassroomApi.programs.list(params) });
}
function progMut<T>(fn: (v: any) => Promise<T>, ok: string) {
  return () => { const qc = useQueryClient(); return useMutation({ mutationFn: fn, onSuccess: () => { qc.invalidateQueries({ queryKey: ["ec-programs"] }); if (ok) toast.success(ok); }, onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed.") }); };
}
export const useCreateEcProgram = progMut((d) => eclassroomApi.programs.create(d), "Program created.");
export const useUpdateEcProgram = progMut((v: { id: string; data: object }) => eclassroomApi.programs.update(v.id, v.data), "Saved.");
export const useDeleteEcProgram = progMut((id: string) => eclassroomApi.programs.remove(id), "Removed.");

// ── Schedules / Broadcast ─────────────────────────────────────────────────────
export function useEcSchedules(params?: { status?: string; year_group_id?: string; session_id?: string }) {
  return useQuery<EcSchedule[]>({ queryKey: ["ec-schedules", params], queryFn: () => eclassroomApi.schedules.list(params) });
}
function schedMut<T>(fn: (v: any) => Promise<T>, ok: string) {
  return () => { const qc = useQueryClient(); return useMutation({ mutationFn: fn, onSuccess: () => { qc.invalidateQueries({ queryKey: ["ec-schedules"] }); if (ok) toast.success(ok); }, onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed.") }); };
}
export const useCreateEcSchedule = schedMut((d) => eclassroomApi.schedules.create(d), "Schedule created.");
export const useUpdateEcSchedule = schedMut((v: { id: string; data: object }) => eclassroomApi.schedules.update(v.id, v.data), "Saved.");
export const useDeleteEcSchedule = schedMut((id: string) => eclassroomApi.schedules.remove(id), "Removed.");
export const useEndEcBroadcast = schedMut((id: string) => eclassroomApi.schedules.end(id), "Broadcast ended.");
// goLive returns the schedule (with live_session_id) — caller navigates to the room.
export function useGoLiveEcSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => eclassroomApi.schedules.goLive(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ec-schedules"] }); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t go live."),
  });
}
