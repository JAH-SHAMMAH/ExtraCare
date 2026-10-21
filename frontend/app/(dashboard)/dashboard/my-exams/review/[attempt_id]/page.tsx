"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Loader2, CheckCircle2, XCircle, ArrowLeft } from "lucide-react";
import { cbtApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { renderQuestionHtml } from "@/components/inputs/MathTools";

interface Item {
  question_id: string; question_text: string; question_type: string;
  options: ({ key: string; text: string } | string)[] | null;
  your_answer: string | null; correct_answer: string | null; is_correct: boolean;
}

const label = (item: Item, key: string | null) => {
  if (!key) return "No answer";
  const opt = (item.options || []).find((o) => (typeof o === "string" ? o : o.key) === key);
  const text = opt ? (typeof opt === "string" ? opt : opt.text) : "";
  return text ? `${key.toUpperCase()}. ${text}` : key;
};

export default function PracticeReviewPage() {
  const { attempt_id } = useParams() as { attempt_id: string };
  const { data, isLoading, error } = useQuery({
    queryKey: ["practice-review", attempt_id],
    queryFn: () => cbtApi.practice.review(attempt_id),
  });

  if (isLoading) return <div className="p-8 flex justify-center"><Loader2 className="animate-spin text-brand-600" /></div>;
  if (error || !data) {
    return (
      <div className="p-8 max-w-2xl mx-auto text-center">
        <p className="text-slate-600 mb-3">This review isn't available.</p>
        <Link href="/dashboard/my-exams?tab=practice" className="text-brand-600 font-semibold text-sm">Back to practice</Link>
      </div>
    );
  }
  const items = data.items as Item[];
  const right = items.filter((i) => i.is_correct).length;
  return (
    <div className="p-4 sm:p-8 max-w-3xl mx-auto">
      <Link href="/dashboard/my-exams?tab=practice" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-4"><ArrowLeft size={15} /> Practice</Link>
      <h1 className="text-2xl font-black text-slate-900">Review</h1>
      <p className="text-slate-500 text-sm mb-6">You got <b className="text-slate-800">{right}</b> of <b className="text-slate-800">{items.length}</b> right.</p>
      <div className="space-y-4">
        {items.map((it, i) => (
          <div key={it.question_id} className={cn("bg-white rounded-xl border p-5", it.is_correct ? "border-emerald-200" : "border-red-200")}>
            <div className="flex items-start gap-3">
              {it.is_correct ? <CheckCircle2 className="text-emerald-600 shrink-0 mt-0.5" size={20} /> : <XCircle className="text-red-600 shrink-0 mt-0.5" size={20} />}
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-bold text-slate-400 mb-1">Question {i + 1}</p>
                <div className="text-sm font-semibold text-slate-900 mb-3" dangerouslySetInnerHTML={{ __html: renderQuestionHtml(it.question_text) }} />
                <p className="text-sm"><span className="text-slate-400">Your answer: </span><span className={it.is_correct ? "text-emerald-700 font-semibold" : "text-red-700 font-semibold"}>{label(it, it.your_answer)}</span></p>
                {!it.is_correct && <p className="text-sm mt-1"><span className="text-slate-400">Correct answer: </span><span className="text-emerald-700 font-semibold">{label(it, it.correct_answer)}</span></p>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
