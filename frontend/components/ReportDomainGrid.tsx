/**
 * Reusable grid for rating entry: rows=students, cols=domains, cells=dropdowns.
 * Used in report-entry for teacher data entry, and report-cards for display.
 */

import { useMemo } from 'react';
import { Loader2 } from 'lucide-react';
import { AssessmentDomain, StudentDomainRating } from '@/hooks/useAssessmentDomains';

interface ReportDomainGridProps {
  domains: AssessmentDomain[];
  students: Array<{ id: string; student_id: string; full_name?: string }>;
  ratings: StudentDomainRating[];
  readOnly?: boolean;
  onRatingChange?: (studentId: string, domainId: string, rating: string | null, comment?: string) => void;
  isLoading?: boolean;
}

export function ReportDomainGrid({
  domains,
  students,
  ratings,
  readOnly = false,
  onRatingChange,
  isLoading = false,
}: ReportDomainGridProps) {
  // Index ratings by student+domain for O(1) lookup
  const ratingMap = useMemo(() => {
    const map = new Map<string, StudentDomainRating>();
    ratings.forEach((r) => {
      map.set(`${r.student_id}:${r.domain_id}`, r);
    });
    return map;
  }, [ratings]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin mr-2" size={20} />
        <span className="text-slate-500">Loading domains...</span>
      </div>
    );
  }

  if (!domains.length) {
    return (
      <div className="bg-white rounded-xl border border-dashed border-slate-200 p-8 text-center">
        <p className="text-sm text-slate-500">No domains set up for this section yet.</p>
      </div>
    );
  }

  if (!students.length) {
    return (
      <div className="bg-white rounded-xl border border-dashed border-slate-200 p-8 text-center">
        <p className="text-sm text-slate-500">No students in this class.</p>
      </div>
    );
  }

  // Group domains by type
  const domainsByType = domains.reduce(
    (acc, d) => {
      const key = d.domain_type;
      if (!acc[key]) acc[key] = [];
      acc[key].push(d);
      return acc;
    },
    {} as Record<string, AssessmentDomain[]>
  );

  return (
    <div className="space-y-8">
      {Object.entries(domainsByType).map(([type, typeDomains]) => (
        <div key={type} className="bg-white rounded-xl border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-900 mb-4 capitalize">{type} Skills</h3>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="text-left font-semibold text-slate-700 px-4 py-2 w-32">Student</th>
                  {typeDomains.map((d) => (
                    <th key={d.id} className="text-center font-semibold text-slate-700 px-2 py-2 w-24">
                      <div className="text-xs">{d.name}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {students.map((student, idx) => (
                  <tr key={student.id} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                    <td className="font-mono text-xs text-slate-600 px-4 py-3 border-r border-slate-200">
                      <div>{student.student_id}</div>
                      <div className="text-slate-500">{student.full_name || '—'}</div>
                    </td>
                    {typeDomains.map((domain) => {
                      const rating = ratingMap.get(`${student.id}:${domain.id}`);
                      return (
                        <td key={domain.id} className="text-center px-2 py-3 border-r border-slate-200">
                          {readOnly ? (
                            <div className="text-sm font-medium text-slate-700">
                              {rating?.rating || '—'}
                              {rating?.comment && <div className="text-xs text-slate-500 mt-1">{rating.comment}</div>}
                            </div>
                          ) : (
                            <select
                              value={rating?.rating || ''}
                              onChange={(e) => {
                                onRatingChange?.(student.id, domain.id, e.target.value || null);
                              }}
                              className="w-full px-2 py-1 text-xs border border-slate-300 rounded bg-white text-slate-700 hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
                            >
                              <option value="">—</option>
                              <option value="Excellent">Excellent</option>
                              <option value="Good">Good</option>
                              <option value="Fair">Fair</option>
                              <option value="Poor">Poor</option>
                            </select>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
