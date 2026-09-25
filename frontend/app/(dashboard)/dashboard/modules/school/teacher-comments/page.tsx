"use client";

import { CommentGridTab } from "@/components/reports/ReportCardPrint";
import { MessageSquareText } from "lucide-react";

/**
 * Teacher Comments — the PC (pastoral-care) teacher's comment for each pupil in
 * their class, for one term and sub-term.
 *
 * Reuses CommentGridTab, the same editor Reports View renders as a tab. Nothing
 * here is new: the store (StudentReportComment), the endpoints
 * (GET/POST /platform/report-comments) and the gate (_gate_comment_access) all
 * existed and worked. What was missing was a way to reach them — the editor was
 * buried inside Reports View, which is class-teacher-only and which, until
 * recently, refused every teacher because teacher_sections was empty.
 *
 * PC comments only. The HEAD comment is admin-only and stays on Reports View;
 * putting it here would offer teachers a grid the API refuses every time.
 *
 * WHO CAN SAVE is narrower than who can open this page: _gate_comment_access
 * limits PC comments to that class's PC teacher, so a subject teacher is refused
 * per class rather than at the door. That is deliberate and unchanged - whether
 * any subject teacher should be able to comment is a question with Fairview, not
 * something to settle by loosening the gate.
 */
export default function TeacherCommentsPage() {
  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
        <span>School Report</span><span>/</span>
        <span className="text-brand-600 font-semibold">Teacher Comments</span>
      </nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2">
        <MessageSquareText size={22} className="text-brand-600" /> Teacher Comments
      </h1>
      <p className="text-slate-500 text-sm mb-5">
        Your comment on each pupil for the term. These print on the report card, under
        the PC Teacher&rsquo;s Comment.
      </p>

      <CommentGridTab kind="pc" label="PC Comment" />
    </div>
  );
}
