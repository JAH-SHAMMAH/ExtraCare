/**
 * React Query hooks for assessment domain and student rating CRUD.
 * Supports domain setup (admin) and student rating entry (teachers).
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export interface AssessmentDomain {
  id: string;
  section_id: string;
  domain_type: 'psychomotor' | 'affective';
  name: string;
  rating_scale_id: string | null;
  position: number;
}

export interface StudentDomainRating {
  // Optional: rows flattened out of the class-scoped grid are keyed by
  // (student_id, domain_id) and carry no row id of their own.
  id?: string;
  student_id: string;
  // An AcademicTerm id since migration 130 — never a name.
  term_id?: string;
  term_name?: string | null;
  domain_id: string;
  rating: string | null;
  comment: string | null;
}

// ── Domain CRUD Hooks ──────────────────────────────────────────────────────

export function useAssessmentDomains(sectionId?: string, domainType?: string) {
  return useQuery({
    queryKey: ['assessmentDomains', sectionId, domainType],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (sectionId) params.append('section_id', sectionId);
      if (domainType) params.append('domain_type', domainType);

      const response = await fetch(`/api/v1/reports/domains?${params}`, {
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Failed to fetch domains');
      return response.json() as Promise<AssessmentDomain[]>;
    },
  });
}

export function useCreateDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: {
      section_id: string;
      domain_type: 'psychomotor' | 'affective';
      name: string;
      rating_scale_id?: string | null;
      position?: number;
    }) => {
      const response = await fetch('/api/v1/reports/domains', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Failed to create domain');
      return response.json() as Promise<AssessmentDomain>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assessmentDomains'] });
    },
  });
}

export function useUpdateDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      payload,
    }: {
      id: string;
      payload: {
        name?: string;
        rating_scale_id?: string | null;
        position?: number;
      };
    }) => {
      const response = await fetch(`/api/v1/reports/domains/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Failed to update domain');
      return response.json() as Promise<AssessmentDomain>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assessmentDomains'] });
    },
  });
}

export function useDeleteDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await fetch(`/api/v1/reports/domains/${id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Failed to delete domain');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assessmentDomains'] });
    },
  });
}

// ── Student Rating Hooks ───────────────────────────────────────────────────

// Domain RATINGS deliberately do not live here any more.
//
// This file used to carry useStudentDomainRatings / useUpsertStudentRatings, which
// called /api/v1/reports/students/{id}/domain-ratings with a raw fetch. That path
// was dead three times over: the endpoint required school:assessments:write, a
// scope no teacher held; it had no class scoping at all; and the raw fetch sent no
// Authorization header, so it 401'd with cookie-auth off and tripped CSRF with it
// on. The caller also passed a term ID into a field the endpoint matched by NAME.
//
// The ratings endpoints in reports.py have been retired. Use the school.py pair
// instead, already wired and correctly gated:
//
//   useDomainRatings(student_id, term_id)   — read  (hooks/useSchool)
//   useSaveDomainRatings()                 — write (hooks/useSchool)
//
// Both go through the axios client, so they carry auth, and the write is gated to
// the pupil's class teacher.
