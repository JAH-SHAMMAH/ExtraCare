"use client";

import { useState } from "react";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { TermsTab, TermDatesTab, AttendanceTab, DeadlineTab, CommentTab, DefaultCommentTab, GradingSystemTab, BrandingTab, ResultTypeTab, ResultPhotoTab, ExclusionTab } from "@/components/reports/ReportSetupTabs";
import { AssessmentGroupTab, AssessmentTab } from "@/components/reports/ReportAssessmentTabs";
import { ResultViewTab } from "@/components/reports/ReportResultViewTab";
import { BehaviourSkillsTab } from "@/components/reports/BehaviourSkillsTab";
import { cn } from "@/lib/utils";
import { Settings2 } from "lucide-react";

// Educare's full Report Setup tab set. Built in S-0: Terms & Sub-term, Term
// Begins/Ends Date, Attendance Setup, Deadline. The rest arrive in S-1…S-3.
type Tab =
  | "terms" | "comment" | "grading" | "assessment-group" | "assessment"
  | "non-assessment" | "default-comment" | "term-dates" | "deadline"
  | "attendance" | "branding" | "result-type" | "photo" | "exclusion" | "result-view" | "behaviour-skills";

const TABS: [Tab, string][] = [
  ["terms", "Terms & Sub-term"], ["comment", "Comment"], ["grading", "Grading System"],
  ["assessment-group", "Assessment Group"], ["assessment", "Assessment"],
  ["non-assessment", "Non Assessment Comment"], ["behaviour-skills", "Behaviour & Skills"],
  ["default-comment", "Result Default Comment"],
  ["term-dates", "Term Begins/Ends Date"], ["deadline", "Deadline"], ["attendance", "Attendance Setup"],
  ["branding", "School Motto, Seal & Sponsor"], ["result-type", "Result Type"],
  ["photo", "Result Photo Setup"], ["exclusion", "Subjects For Score Exclusion"], ["result-view", "Result View"],
];

const LIVE = new Set<Tab>(["terms", "comment", "grading", "assessment-group", "assessment", "default-comment", "behaviour-skills", "term-dates", "attendance", "deadline", "branding", "result-type", "photo", "exclusion", "result-view"]);

export default function ReportSetupPage() {
  const canWrite = useHasPermission("settings:write");
  const [tab, setTab] = useState<Tab>("terms");

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Secondary School Report</span><span>/</span><span className="text-brand-600 font-semibold">Report Setup</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><Settings2 size={22} className="text-brand-600" /> Report Setup</h1>
      <p className="text-slate-500 text-sm mb-5">Configuration hub for the report-card engine. Terms, dates, attendance and deadlines are live; the assessment &amp; result-view tabs arrive in later batches.</p>

      <div className="flex flex-wrap gap-1 border-b border-slate-200 mb-6">
        {TABS.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-3 py-2 text-sm font-semibold border-b-2 -mb-px transition whitespace-nowrap", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700", !LIVE.has(k) && "opacity-60")}>{l}</button>
        ))}
      </div>

      {tab === "terms" ? <TermsTab canWrite={canWrite} />
        : tab === "comment" ? <CommentTab canWrite={canWrite} />
        : tab === "grading" ? <GradingSystemTab canWrite={canWrite} />
        : tab === "default-comment" ? <DefaultCommentTab canWrite={canWrite} />
        : tab === "term-dates" ? <TermDatesTab canWrite={canWrite} />
        : tab === "attendance" ? <AttendanceTab canWrite={canWrite} />
        : tab === "deadline" ? <DeadlineTab canWrite={canWrite} />
        : tab === "branding" ? <BrandingTab canWrite={canWrite} />
        : tab === "result-type" ? <ResultTypeTab canWrite={canWrite} />
        : tab === "photo" ? <ResultPhotoTab canWrite={canWrite} />
        : tab === "exclusion" ? <ExclusionTab canWrite={canWrite} />
        : tab === "assessment-group" ? <AssessmentGroupTab canWrite={canWrite} />
        : tab === "assessment" ? <AssessmentTab canWrite={canWrite} />
        : tab === "result-view" ? <ResultViewTab canWrite={canWrite} />
        : tab === "behaviour-skills" ? <BehaviourSkillsTab canWrite={canWrite} />
        : <Placeholder label={TABS.find(([k]) => k === tab)?.[1] ?? ""} />}
    </div>
  );
}

function Placeholder({ label }: { label: string }) {
  return (
    <div className="bg-white rounded-xl border border-dashed border-slate-200 p-12 text-center">
      <Settings2 size={30} className="mx-auto mb-3 text-slate-300" />
      <p className="text-sm font-semibold text-slate-600">{label}</p>
      <p className="text-xs text-slate-400 mt-1">Arrives in an upcoming batch of the Secondary Report parity build-out.</p>
    </div>
  );
}
