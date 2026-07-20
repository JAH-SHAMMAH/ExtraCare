"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { hrExtApi } from "@/lib/api";

function inv(qc: ReturnType<typeof useQueryClient>, keys: string[]) {
  keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}
function mut<T>(fn: (v: any) => Promise<T>, keys: string[], ok: string) {
  return () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: fn,
      onSuccess: () => { inv(qc, keys); if (ok) toast.success(ok); },
      onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed."),
    });
  };
}

// ── Recruitment ───────────────────────────────────────────────────────────────
export function useJobs(status?: string) { return useQuery<any[]>({ queryKey: ["hr-jobs", status], queryFn: () => hrExtApi.jobs.list(status) }); }
export function useApplicants(jobId?: string) { return useQuery<any[]>({ queryKey: ["hr-applicants", jobId], queryFn: () => hrExtApi.applicants.list(jobId), enabled: !!jobId }); }
export const useCreateJob = mut((d) => hrExtApi.jobs.create(d), ["hr-jobs", "hr-stats"], "Job opening created.");
export const useUpdateJob = mut((v: { id: string; data: object }) => hrExtApi.jobs.update(v.id, v.data), ["hr-jobs", "hr-stats"], "Updated.");
export const useDeleteJob = mut((id: string) => hrExtApi.jobs.remove(id), ["hr-jobs", "hr-stats"], "Removed.");
export const useCreateApplicant = mut((d) => hrExtApi.applicants.create(d), ["hr-applicants", "hr-jobs"], "Applicant added.");
export const useUpdateApplicant = mut((v: { id: string; data: object }) => hrExtApi.applicants.update(v.id, v.data), ["hr-applicants"], "Updated.");
export const useDeleteApplicant = mut((id: string) => hrExtApi.applicants.remove(id), ["hr-applicants", "hr-jobs"], "Removed.");

// ── Disciplinary ──────────────────────────────────────────────────────────────
export function useCases(status?: string) { return useQuery<any[]>({ queryKey: ["hr-cases", status], queryFn: () => hrExtApi.cases.list(status) }); }
// Self-service: the caller's OWN disciplinary records (Discipline › My Actions).
export function useMyCases() { return useQuery<any[]>({ queryKey: ["hr-my-cases"], queryFn: () => hrExtApi.cases.mine() }); }
export const useCreateCase = mut((d) => hrExtApi.cases.create(d), ["hr-cases", "hr-stats"], "Case opened.");
export const useUpdateCase = mut((v: { id: string; data: object }) => hrExtApi.cases.update(v.id, v.data), ["hr-cases", "hr-stats"], "Updated.");
export const useDeleteCase = mut((id: string) => hrExtApi.cases.remove(id), ["hr-cases", "hr-stats"], "Removed.");

// ── Appointments (Appointment Manager) ─────────────────────────────────────────
export function useAppointments(params?: { staff_user_id?: string; status?: string }) { return useQuery<any[]>({ queryKey: ["hr-appointments", params], queryFn: () => hrExtApi.appointments.list(params) }); }
export const useCreateAppointment = mut((d) => hrExtApi.appointments.create(d), ["hr-appointments"], "Appointment recorded.");
export const useUpdateAppointment = mut((v: { id: string; data: object }) => hrExtApi.appointments.update(v.id, v.data), ["hr-appointments"], "Updated.");
export const useDeleteAppointment = mut((id: string) => hrExtApi.appointments.remove(id), ["hr-appointments"], "Removed.");

// ── Stats (dashboard cards) ─────────────────────────────────────────────────────
export function useHrStats() { return useQuery<{ open_jobs: number; total_applicants: number; open_disciplinary: number }>({ queryKey: ["hr-stats"], queryFn: () => hrExtApi.stats() }); }
