"use client";

import { useState } from "react";
import { useClasses, useGradePublishStatus, usePublishGrades } from "@/hooks/useSchool";
import { cn } from "@/lib/utils";
import { CheckCircle2, EyeOff, Loader2, ShieldAlert, Send } from "lucide-react";
import type { SchoolClass } from "@/types";

/**
 * Result Publish Helper — bulk publish/unpublish a class's grades for a term.
 * Grades default to draft (hidden from parents/students); publishing finalises
 * them so they appear on the report card. Correctness feature: nothing a teacher
 * is still working on leaks downstream until it's explicitly published.
 */
export default function ResultPublishPage() {
  const [classId, setClassId] = useState("");
  const [term, setTerm] = useState("Term 1");

  const { data: classesData } = useClasses({ page_size: 100 });
  const classes: SchoolClass[] = classesData?.items || [];

  const ready = !!classId && !!term;
  const { data: status, isLoading } = useGradePublishStatus({ term, class_id: classId || undefined });
  const publish = usePublishGrades();

  const total = status?.total ?? 0;
  const published = status?.published ?? 0;
  const draft = status?.draft ?? 0;
  const pct = total > 0 ? Math.round((published / total) * 100) : 0;

  const run = (s: "published" | "draft") =>
    publish.mutate({ term, status: s, class_id: classId });

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Result Publish</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Result Publish Helper</h1>
        <p className="text-slate-500 text-sm mt-0.5">Publish a class&apos;s finalised results for a term. Until published, grades stay hidden from parents and students.</p>
      </div>

      {/* Scope pickers */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="label">Class</label>
          <select value={classId} onChange={(e) => setClassId(e.target.value)} className="input">
            <option value="">— Select class —</option>
            {classes.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
          </select>
        </div>
        <div>
          <label className="label">Term</label>
          <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="e.g. Term 1" className="input" />
        </div>
      </div>

      {!ready ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <ShieldAlert size={38} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-slate-500">Select a class and term</p>
          <p className="text-sm mt-1">Choose what to review before publishing.</p>
        </div>
      ) : isLoading ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : total === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <EyeOff size={34} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-slate-500">No grades for this class + term yet</p>
          <p className="text-sm mt-1">Enter marks in Exams first, then publish here.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          {/* Summary */}
          <div className="flex items-center gap-6 mb-5">
            <div className="text-center">
              <p className="text-3xl font-black text-slate-900 tabular-nums">{pct}%</p>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mt-1">Published</p>
            </div>
            <div className="flex-1">
              <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
              </div>
              <div className="flex items-center gap-4 mt-2 text-xs">
                <span className="inline-flex items-center gap-1.5 text-emerald-600"><CheckCircle2 size={13} />{published} published</span>
                <span className="inline-flex items-center gap-1.5 text-amber-600"><EyeOff size={13} />{draft} draft</span>
                <span className="text-slate-400">· {total} total</span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t border-slate-100">
            <button
              onClick={() => run("published")}
              disabled={publish.isPending || draft === 0}
              className="btn-primary gap-2 flex-1 justify-center"
              title={draft === 0 ? "Everything is already published" : "Make all grades visible to parents/students"}
            >
              {publish.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
              Publish all {draft > 0 ? `(${draft})` : ""}
            </button>
            <button
              onClick={() => run("draft")}
              disabled={publish.isPending || published === 0}
              className={cn("btn-secondary gap-2 flex-1 justify-center", published === 0 && "opacity-50")}
              title={published === 0 ? "Nothing is published" : "Hide all grades from parents/students again"}
            >
              <EyeOff size={15} /> Unpublish all
            </button>
          </div>
          <p className="text-[11px] text-slate-400 mt-3 flex items-center gap-1.5">
            <ShieldAlert size={12} /> Publishing makes these grades visible to parents and students immediately.
          </p>
        </div>
      )}
    </div>
  );
}
