"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { schoolApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { FileText, CheckCircle2, AlertCircle, Loader2, Eye } from "lucide-react";

interface ReportApproval {
  id: string;
  class_id?: string;
  class_name?: string;
  academic_year?: string;
  term?: string;
  stage: "draft" | "submitted" | "reviewed" | "approved" | "published";
  created_at: string;
}

const STAGE_LABELS: Record<ReportApproval["stage"], { label: string; color: string }> = {
  draft: { label: "Draft", color: "bg-slate-100 text-slate-700 border-slate-200" },
  submitted: { label: "Unattended To", color: "bg-yellow-50 text-yellow-700 border-yellow-200" },
  reviewed: { label: "Reviewed", color: "bg-blue-50 text-blue-700 border-blue-200" },
  approved: { label: "Approved", color: "bg-green-50 text-green-700 border-green-200" },
  published: { label: "Published", color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
};

export default function TeacherReportsPage() {
  const [detailId, setDetailId] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["teacher-reports"],
    queryFn: async () => {
      const response = await fetch("/api/academics/report-workflow/mine");
      if (!response.ok) throw new Error("Failed to fetch teacher reports");
      return response.json();
    },
  });

  const reports = data?.items || [];

  if (detailId) {
    const report = reports.find((r: ReportApproval) => r.id === detailId);
    if (report) {
      return <ReportDetail report={report} onBack={() => setDetailId(null)} />;
    }
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Education</span>
          <span>/</span>
          <span className="text-brand-600 font-semibold">Teacher Reports</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Teacher Reports</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          View your report submissions and their approval status.
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-10 text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : reports.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-20 text-slate-400">
          <FileText size={40} className="mb-3 opacity-40" />
          <p className="font-semibold">No reports submitted yet</p>
          <p className="text-sm mt-1">Your submitted reports will appear here.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-5 py-3 text-xs font-bold text-slate-700 uppercase">Date</th>
                <th className="text-left px-5 py-3 text-xs font-bold text-slate-700 uppercase">Class</th>
                <th className="text-left px-5 py-3 text-xs font-bold text-slate-700 uppercase">Term</th>
                <th className="text-left px-5 py-3 text-xs font-bold text-slate-700 uppercase">Status</th>
                <th className="text-right px-5 py-3 text-xs font-bold text-slate-700 uppercase">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {reports.map((report: ReportApproval) => (
                <tr key={report.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-4 text-sm text-slate-700">
                    {formatDate(report.created_at)}
                  </td>
                  <td className="px-5 py-4 text-sm text-slate-700">{report.class_name || "—"}</td>
                  <td className="px-5 py-4 text-sm text-slate-700">{report.term || "—"}</td>
                  <td className="px-5 py-4">
                    <span
                      className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${
                        STAGE_LABELS[report.stage].color
                      }`}
                    >
                      {report.stage === "submitted" || report.stage === "reviewed" ? (
                        <AlertCircle size={12} />
                      ) : report.stage === "published" ? (
                        <CheckCircle2 size={12} />
                      ) : null}
                      {STAGE_LABELS[report.stage].label}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right">
                    <button
                      onClick={() => setDetailId(report.id)}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-600 hover:text-brand-700"
                    >
                      <Eye size={14} />
                      Check Result
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ReportDetail({
  report,
  onBack,
}: {
  report: ReportApproval;
  onBack: () => void;
}) {
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <button
        onClick={onBack}
        className="mb-6 text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1.5"
      >
        ← Back to Reports
      </button>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="mb-6">
          <h2 className="text-lg font-black text-slate-900 mb-2">
            Viewing Results For {report.class_name || "Class"}
          </h2>
          <p className="text-sm text-slate-500">
            {report.academic_year} {report.term ? `• ${report.term}` : ""}
          </p>
        </div>

        <div className="mb-6 p-4 bg-slate-50 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase text-slate-500 mb-1">Result Approval Status</p>
              <p className="text-sm font-bold text-slate-900">{STAGE_LABELS[report.stage].label}</p>
            </div>
            <span className={`inline-flex text-xs font-semibold px-3 py-1 rounded-full border ${STAGE_LABELS[report.stage].color}`}>
              {report.stage === "submitted" && "PENDING"}
              {report.stage === "reviewed" && "UNDER REVIEW"}
              {report.stage === "approved" && "APPROVED"}
              {report.stage === "published" && "PUBLISHED"}
              {report.stage === "draft" && "DRAFT"}
            </span>
          </div>
        </div>

        <div className="border-t border-slate-200 pt-6">
          <p className="text-sm text-slate-600 text-center py-8">
            Student results table would be displayed here when integrated with the report-card component.
          </p>
        </div>
      </div>
    </div>
  );
}
