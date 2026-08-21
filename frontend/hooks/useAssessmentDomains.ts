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
  id: string;
  student_id: string;
  term: string;
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

export function useStudentDomainRatings(studentId: string, term?: string) {
  return useQuery({
    queryKey: ['studentDomainRatings', studentId, term],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (term) params.append('term', term);

      const response = await fetch(`/api/v1/reports/students/${studentId}/domain-ratings?${params}`, {
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Failed to fetch ratings');
      return response.json() as Promise<StudentDomainRating[]>;
    },
    enabled: !!studentId,
  });
}

export function useUpsertStudentRatings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      studentId,
      term,
      ratings,
    }: {
      studentId: string;
      term: string;
      ratings: Array<{
        domain_id: string;
        rating?: string | null;
        comment?: string | null;
      }>;
    }) => {
      const response = await fetch(`/api/v1/reports/students/${studentId}/domain-ratings/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term, ratings }),
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Failed to save ratings');
      return response.json();
    },
    onSuccess: (_, { studentId, term }) => {
      queryClient.invalidateQueries({
        queryKey: ['studentDomainRatings', studentId, term],
      });
    },
  });
}
