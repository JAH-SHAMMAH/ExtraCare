"use client";

import { useRouter } from "next/navigation";
import { useCBTExams } from "@/hooks/useSchoolExperience";
import { cn, formatDate } from "@/lib/utils";
import { MonitorCheck, Clock, Award } from "lucide-react";
import type { CBTExam } from "@/types";

/**
 * Student-only My Exams page
 *
 * Independent of the admin /cbt tree. Gated via CORE_NAV roleOnly: "student"
 * with no permission check — fully own-record scoped server-side via
 * useCBTExams({ for_me: true }) which filters by student.class_id.
 *
 * Reuses the verified backend scoping from Migration 121: students hold
 * school:cbt:sit (sit in exam only), no admin/read scopes.
 */

export default function MyExamsPage() {
  const { data, isLoading } = useCBTExams({
    for_me: true,
    page: 1,
    page_size: 50,
  });

  const exams = data?.items as CBTExam[] | undefined;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Education</span>
          <span>/</span>
          <span className="text-brand-600 font-semibold">My Exams</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Exams</h1>
        <p className="text-slate-500 text-sm mt-0.5">View your assigned exams and results.</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-40 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : exams && exams.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {exams.map((exam) => (
            <StudentExamCard key={exam.id} exam={exam} />
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-20 text-slate-400">
          <MonitorCheck size={40} className="mb-3 opacity-40" />
          <p className="font-semibold">No exams assigned yet</p>
          <p className="text-sm mt-1">Exams will appear here when your teacher posts them.</p>
        </div>
      )}
    </div>
  );
}

function StudentExamCard({ exam }: { exam: CBTExam }) {
  const router = useRouter();
  const now = new Date();
  const startTime = exam.start_time ? new Date(exam.start_time) : null;
  const endTime = exam.end_time ? new Date(exam.end_time) : null;
  const isLive = startTime && endTime && now >= startTime && now <= endTime;
  const isUpcoming = startTime && now < startTime;
  const isClosed = exam.status === "closed" || (endTime && now > endTime);

  const statusLabel = isClosed ? "Closed" : isLive ? "In Progress" : isUpcoming ? "Upcoming" : "Not Started";
  const statusColor = isClosed ? "text-amber-600" : isLive ? "text-emerald-600" : isUpcoming ? "text-blue-600" : "text-slate-600";

  const handleStartExam = () => {
    router.push(`/dashboard/my-exams/${exam.id}/take`);
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-lg bg-sky-50 border border-sky-100 flex items-center justify-center shrink-0">
          <MonitorCheck size={18} className="text-sky-600" />
        </div>
        <span className={cn("text-xs font-semibold", statusColor)}>{statusLabel}</span>
      </div>
      <h3 className="text-sm font-bold text-slate-900 mb-1 line-clamp-2">{exam.title}</h3>
      {exam.description && <p className="text-xs text-slate-500 mb-3 line-clamp-2">{exam.description}</p>}
      <div className="space-y-1.5 mb-3">
        {startTime && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Clock size={12} />
            {formatDate(exam.start_time || "")} {exam.duration_minutes ? `(${exam.duration_minutes} min)` : ""}
          </div>
        )}
        {exam.pass_percentage && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Award size={12} />
            Pass: {exam.pass_percentage}%
          </div>
        )}
      </div>
      <div className="pt-3 border-t border-slate-100">
        {isLive ? (
          <button
            onClick={handleStartExam}
            className="w-full text-xs font-semibold text-emerald-600 hover:text-emerald-700 transition"
          >
            Resume Exam →
          </button>
        ) : isClosed ? (
          <div className="text-xs text-slate-400 text-center">Exam closed</div>
        ) : isUpcoming ? (
          <div className="text-xs text-blue-600 text-center">Not yet available</div>
        ) : (
          <button
            onClick={handleStartExam}
            className="w-full text-xs font-semibold text-brand-600 hover:text-brand-700 transition"
          >
            Start Exam →
          </button>
        )}
      </div>
    </div>
  );
}
