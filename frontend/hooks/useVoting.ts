"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { votingApi } from "@/lib/api";

export type VPeriod = { id: string; name: string; starts_at: string | null; ends_at: string | null; status: string; section_id: string | null; section_name: string | null; created_at: string; org_id: string };
export type VCategory = { id: string; description: string; section_id: string | null; section_name: string | null; is_active: boolean; created_at: string; org_id: string };
export type VSession = { id: string; title: string; instructions: string | null; starts_at: string | null; ends_at: string | null; session_id: string | null; section_id: string | null; positions: number; candidate_role: string | null; voter_role: string | null; status: string; result_published: boolean; category_ids: string[]; candidate_count: number; total_ballots: number; created_at: string; org_id: string };
export type VCandidate = { id: string; session_id: string; category_id: string; user_id: string; name: string | null; votes: number };
export type VResults = { session_id: string; title: string; status: string; result_published: boolean; positions: number; categories: { category_id: string; category_description: string | null; total_votes: number; candidates: VCandidate[]; winner_ids: string[] }[] };

function m<T>(fn: (v: any) => Promise<T>, keys: string[], ok: string) {
  return () => { const qc = useQueryClient(); return useMutation({ mutationFn: fn, onSuccess: () => { keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] })); if (ok) toast.success(ok); }, onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed.") }); };
}

// ── Periods ─────────────────────────────────────────────────────────────────
export function usePeriods() { return useQuery<VPeriod[]>({ queryKey: ["v-periods"], queryFn: () => votingApi.periods.list() }); }
export const useCreatePeriod = m((d) => votingApi.periods.create(d), ["v-periods"], "Period added.");
export const useExtendPeriod = m((v: { id: string; data: object }) => votingApi.periods.extend(v.id, v.data), ["v-periods"], "Extended.");
export const useDeletePeriod = m((id: string) => votingApi.periods.remove(id), ["v-periods"], "Removed.");

// ── Categories ──────────────────────────────────────────────────────────────
export function useVCategories() { return useQuery<VCategory[]>({ queryKey: ["v-categories"], queryFn: () => votingApi.categories.list() }); }
export const useCreateVCategory = m((d) => votingApi.categories.create(d), ["v-categories"], "Category added.");
export const useUpdateVCategory = m((v: { id: string; data: object }) => votingApi.categories.update(v.id, v.data), ["v-categories"], "Saved.");
export const useDeleteVCategory = m((id: string) => votingApi.categories.remove(id), ["v-categories"], "Removed.");

// ── Sessions ────────────────────────────────────────────────────────────────
export function useVSessions(params?: { status?: string; session_id?: string }) { return useQuery<VSession[]>({ queryKey: ["v-sessions", params], queryFn: () => votingApi.sessions.list(params) }); }
export const useCreateVSession = m((d) => votingApi.sessions.create(d), ["v-sessions"], "Vote session created.");
export const useUpdateVSession = m((v: { id: string; data: object }) => votingApi.sessions.update(v.id, v.data), ["v-sessions"], "Saved.");
export const useDeleteVSession = m((id: string) => votingApi.sessions.remove(id), ["v-sessions"], "Removed.");
export const useOpenVSession = m((id: string) => votingApi.sessions.open(id), ["v-sessions"], "Voting opened.");
export const useConductVSession = m((id: string) => votingApi.sessions.conduct(id), ["v-sessions"], "Voting closed.");
export const usePublishVSession = m((id: string) => votingApi.sessions.publish(id), ["v-sessions"], "Result published.");

export function useVResults(sessionId?: string) { return useQuery<VResults>({ queryKey: ["v-results", sessionId], queryFn: () => votingApi.sessions.results(sessionId!), enabled: !!sessionId }); }
export function useVCandidates(sessionId?: string) { return useQuery<VCandidate[]>({ queryKey: ["v-candidates", sessionId], queryFn: () => votingApi.sessions.candidates(sessionId!), enabled: !!sessionId }); }
export const useAddCandidate = m((v: { sessionId: string; data: object }) => votingApi.sessions.addCandidate(v.sessionId, v.data), ["v-candidates", "v-sessions"], "Candidate added.");
export const useRemoveCandidate = m((id: string) => votingApi.removeCandidate(id), ["v-candidates", "v-sessions"], "Removed.");

// ── Voter (My Votes) ──────────────────────────────────────────────────────────
export type VBallot = { session_id: string; title: string; instructions: string | null; categories: { category_id: string; description: string | null; candidates: { id: string; name: string | null }[] }[]; my_votes: Record<string, string> };
export function useOpenVSessions() { return useQuery<VSession[]>({ queryKey: ["v-open"], queryFn: () => votingApi.open() }); }
export function useBallot(sessionId?: string) { return useQuery<VBallot>({ queryKey: ["v-ballot", sessionId], queryFn: () => votingApi.ballot(sessionId!), enabled: !!sessionId }); }
export function useMyVotes(sessionId?: string) { return useQuery<Record<string, string>>({ queryKey: ["v-my-votes", sessionId], queryFn: () => votingApi.myVotes(sessionId!), enabled: !!sessionId }); }
export function useCastVote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { sessionId: string; data: object }) => votingApi.vote(v.sessionId, v.data),
    onSuccess: (_d, v) => { qc.invalidateQueries({ queryKey: ["v-my-votes", v.sessionId] }); qc.invalidateQueries({ queryKey: ["v-ballot", v.sessionId] }); toast.success("Vote cast."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t vote."),
  });
}
