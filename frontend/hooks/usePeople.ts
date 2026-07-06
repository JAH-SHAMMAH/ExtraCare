"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { parentsApi, hrDevApi } from "@/lib/api";
import type { ParentLink, StaffAssessment, TalentCandidate, Paginated } from "@/types";

// ── Parents Directory ────────────────────────────────────────────────────────

export function useParentLinks(params?: { search?: string; page?: number; page_size?: number }) {
  return useQuery<Paginated<ParentLink>>({
    queryKey: ["parents", params],
    queryFn: () => parentsApi.list(params),
  });
}

export function useCreateParentLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { user_id: string; student_id: string; relationship_type?: string; is_primary?: boolean }) =>
      parentsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["parents"] });
      toast.success("Guardian linked.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to link guardian."),
  });
}

export function useUpdateParentLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { relationship_type?: string; is_primary?: boolean } }) =>
      parentsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["parents"] });
      toast.success("Guardian link updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update link."),
  });
}

export function useDeleteParentLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => parentsApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["parents"] });
      toast.success("Guardian unlinked.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to unlink."),
  });
}

// ── Staff Assessment ─────────────────────────────────────────────────────────

export function useStaffAssessments(params?: { staff_user_id?: string; status?: string; page?: number; page_size?: number }) {
  return useQuery<Paginated<StaffAssessment>>({
    queryKey: ["staff-assessments", params],
    queryFn: () => hrDevApi.assessments.list(params),
  });
}

export function useCreateAssessment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => hrDevApi.assessments.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["staff-assessments"] });
      toast.success("Assessment saved.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save assessment."),
  });
}

export function useUpdateAssessment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => hrDevApi.assessments.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["staff-assessments"] });
      toast.success("Assessment updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update assessment."),
  });
}

export function useDeleteAssessment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => hrDevApi.assessments.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["staff-assessments"] });
      toast.success("Assessment removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove assessment."),
  });
}

// ── Talent Pool ──────────────────────────────────────────────────────────────

export function useTalentCandidates(params?: { stage?: string; search?: string; page?: number; page_size?: number }) {
  return useQuery<Paginated<TalentCandidate>>({
    queryKey: ["talent", params],
    queryFn: () => hrDevApi.talent.list(params),
  });
}

export function useCreateCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => hrDevApi.talent.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["talent"] });
      toast.success("Candidate added.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add candidate."),
  });
}

export function useUpdateCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => hrDevApi.talent.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["talent"] });
      toast.success("Candidate updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update candidate."),
  });
}

export function useDeleteCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => hrDevApi.talent.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["talent"] });
      toast.success("Candidate removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove candidate."),
  });
}
