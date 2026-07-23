"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { timetableApi } from "@/lib/api";
import type { TimetableSettings, PeriodGroup, SubjectGroup, SchoolActivity, Period, PeriodSchedule } from "@/types";

function mut<V>(fn: (v: V) => Promise<any>, keys: string[], ok: string) {
  return function useM() {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: fn,
      onSuccess: () => { keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] })); toast.success(ok); },
      onError: (e: any) => toast.error(e?.response?.data?.detail || "Something went wrong."),
    });
  };
}

// ── Settings ──────────────────────────────────────────────────────────────────
export function useTimetableSettings() {
  return useQuery<TimetableSettings>({ queryKey: ["tt-settings"], queryFn: () => timetableApi.settings.get() });
}
export const useUpdateTimetableSettings = mut<object>((d) => timetableApi.settings.update(d), ["tt-settings"], "Settings saved.");

// ── Period groups ─────────────────────────────────────────────────────────────
export function usePeriodGroups() {
  return useQuery<{ items: PeriodGroup[] }>({ queryKey: ["tt-period-groups"], queryFn: () => timetableApi.periodGroups.list() });
}
export const useCreatePeriodGroup = mut<object>((d) => timetableApi.periodGroups.create(d), ["tt-period-groups"], "Period group added.");
export const useUpdatePeriodGroup = mut<{ id: string; data: object }>((v) => timetableApi.periodGroups.update(v.id, v.data), ["tt-period-groups"], "Updated.");
export const useDeletePeriodGroup = mut<string>((id) => timetableApi.periodGroups.delete(id), ["tt-period-groups"], "Removed.");

// ── Subject groups ────────────────────────────────────────────────────────────
export function useSubjectGroups() {
  return useQuery<{ items: SubjectGroup[] }>({ queryKey: ["tt-subject-groups"], queryFn: () => timetableApi.subjectGroups.list() });
}
export const useCreateSubjectGroup = mut<object>((d) => timetableApi.subjectGroups.create(d), ["tt-subject-groups"], "Subject group added.");
export const useUpdateSubjectGroup = mut<{ id: string; data: object }>((v) => timetableApi.subjectGroups.update(v.id, v.data), ["tt-subject-groups"], "Updated.");
export const useDeleteSubjectGroup = mut<string>((id) => timetableApi.subjectGroups.delete(id), ["tt-subject-groups"], "Removed.");

// ── Activities ────────────────────────────────────────────────────────────────
export function useActivities() {
  return useQuery<{ items: SchoolActivity[] }>({ queryKey: ["tt-activities"], queryFn: () => timetableApi.activities.list() });
}
export const useCreateActivity = mut<object>((d) => timetableApi.activities.create(d), ["tt-activities"], "Activity added.");
export const useUpdateActivity = mut<{ id: string; data: object }>((v) => timetableApi.activities.update(v.id, v.data), ["tt-activities"], "Updated.");
export const useDeleteActivity = mut<string>((id) => timetableApi.activities.delete(id), ["tt-activities"], "Removed.");

// ── Periods ─────────────────────────────────────────────────────────────────────
export function usePeriods(params: { period_group_id: string | null; academic_year?: string }) {
  return useQuery<{ items: Period[] }>({
    queryKey: ["tt-periods", params.period_group_id, params.academic_year],
    queryFn: () => timetableApi.periods.list({ period_group_id: params.period_group_id as string, academic_year: params.academic_year }),
    enabled: !!params.period_group_id,
  });
}
export const useCreatePeriod = mut<object>((d) => timetableApi.periods.create(d), ["tt-periods"], "Period added.");
export const useUpdatePeriod = mut<{ id: string; data: object }>((v) => timetableApi.periods.update(v.id, v.data), ["tt-periods"], "Updated.");
export const useDeletePeriod = mut<string>((id) => timetableApi.periods.delete(id), ["tt-periods"], "Removed.");
export const useGeneratePeriods = mut<object>((d) => timetableApi.periods.generate(d), ["tt-periods"], "Periods generated.");

// ── Schedules ───────────────────────────────────────────────────────────────────
export function useSchedules(params: { period_group_id: string | null; academic_year?: string }) {
  return useQuery<{ items: PeriodSchedule[] }>({
    queryKey: ["tt-schedules", params.period_group_id, params.academic_year],
    queryFn: () => timetableApi.schedules.list({ period_group_id: params.period_group_id as string, academic_year: params.academic_year }),
    enabled: !!params.period_group_id,
  });
}
export const useUpsertSchedule = mut<object>((d) => timetableApi.schedules.upsert(d), ["tt-schedules"], "Schedule saved.");
export const useDeleteSchedule = mut<string>((id) => timetableApi.schedules.delete(id), ["tt-schedules"], "Removed.");
