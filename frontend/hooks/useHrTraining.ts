"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { hrTrainingApi } from "@/lib/api";

export type Training = { id: string; title: string; description: string | null; category: string | null; status: string; session_count: number; created_at: string; org_id: string };
export type TrainingSession = { id: string; training_id: string; training_title: string | null; title: string | null; session_date: string | null; start_time: string | null; location: string | null; facilitator: string | null; created_at: string; org_id: string };

function inv(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["hr-trainings"] });
  qc.invalidateQueries({ queryKey: ["hr-training-sessions"] });
  qc.invalidateQueries({ queryKey: ["hr-all-sessions"] });
}
function tMut<T>(fn: (v: any) => Promise<T>, ok: string) {
  return () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: fn,
      onSuccess: () => { inv(qc); if (ok) toast.success(ok); },
      onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed."),
    });
  };
}

export function useTrainings() { return useQuery<Training[]>({ queryKey: ["hr-trainings"], queryFn: () => hrTrainingApi.list() }); }
export function useTrainingSessions(trainingId?: string) { return useQuery<TrainingSession[]>({ queryKey: ["hr-training-sessions", trainingId], queryFn: () => hrTrainingApi.sessions(trainingId!), enabled: !!trainingId }); }
export function useAllSessions() { return useQuery<TrainingSession[]>({ queryKey: ["hr-all-sessions"], queryFn: () => hrTrainingApi.allSessions() }); }

export const useCreateTraining = tMut((d) => hrTrainingApi.create(d), "Training created.");
export const useUpdateTraining = tMut((v: { id: string; data: object }) => hrTrainingApi.update(v.id, v.data), "Saved.");
export const useDeleteTraining = tMut((id: string) => hrTrainingApi.remove(id), "Removed.");
export const useAddSession = tMut((v: { trainingId: string; data: object }) => hrTrainingApi.addSession(v.trainingId, v.data), "Session added.");
export const useUpdateSession = tMut((v: { id: string; data: object }) => hrTrainingApi.updateSession(v.id, v.data), "Saved.");
export const useDeleteSession = tMut((id: string) => hrTrainingApi.removeSession(id), "Removed.");
