"use client";

import { useState } from "react";
import { Star, Loader2, Check } from "lucide-react";
import { toast } from "sonner";
import { useMyTeachers, useRateMyTeacher, type MyTeacher } from "@/hooks/useSchool";
import { cn, getInitials } from "@/lib/utils";

function Stars({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
  return (
    <div className="flex items-center gap-1" role="radiogroup" aria-label={label}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n} star${n > 1 ? "s" : ""}`}
          onClick={() => onChange(n)} className="p-0.5">
          <Star size={26} className={cn(n <= value ? "fill-amber-400 text-amber-400" : "text-slate-300")} />
        </button>
      ))}
    </div>
  );
}

function TeacherCard({ t }: { t: MyTeacher }) {
  const rate = useRateMyTeacher();
  const [stars, setStars] = useState(t.my_rating ?? 0);
  const [comment, setComment] = useState(t.my_comment ?? "");
  const [anon, setAnon] = useState(!!t.my_anonymous);
  const dirty = stars !== (t.my_rating ?? 0) || comment.trim() !== (t.my_comment ?? "") || anon !== !!t.my_anonymous;

  const save = () => {
    if (!stars) return;
    rate.mutate({ teacher_id: t.teacher_id, rating: stars, comment: comment.trim() || undefined, anonymous: anon }, {
      onSuccess: () => toast.success(t.my_rating ? "Rating updated." : "Thanks, your rating was sent."),
      onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Could not save your rating."),
    });
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-11 h-11 rounded-xl bg-violet-600/10 text-violet-700 flex items-center justify-center text-sm font-bold shrink-0">{getInitials(t.name)}</div>
        <div className="min-w-0">
          <p className="font-semibold text-slate-900 truncate">{t.name}</p>
          <p className="text-xs text-slate-500 truncate">
            {t.class_teacher ? "Class teacher" : ""}{t.class_teacher && t.subjects.length ? " · " : ""}{t.subjects.join(", ")}
          </p>
        </div>
        {t.my_rating && !dirty && <span className="ml-auto inline-flex items-center gap-1 text-xs text-emerald-600"><Check size={14} /> Rated</span>}
      </div>
      <Stars value={stars} onChange={setStars} label={`Rate ${t.name}`} />
      <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={1000}
        placeholder="Say something about this teacher (optional)" className="input min-h-[70px] resize-none mt-3" />
      <label className="flex items-center gap-2 mt-3 text-sm text-slate-600 cursor-pointer">
        <input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} className="rounded border-slate-300" />
        Send anonymously <span className="text-xs text-slate-400">(the school won't see your name)</span>
      </label>
      <button onClick={save} disabled={!stars || !dirty || rate.isPending} className="btn-primary gap-2 mt-3">
        {rate.isPending && <Loader2 size={15} className="animate-spin" />}
        {t.my_rating ? "Update rating" : "Submit rating"}
      </button>
    </div>
  );
}

/** Student "Rate My Teachers": the teachers of the pupil's own class, one card each. */
export default function MyTeachersPage() {
  const { data, isLoading, error } = useMyTeachers();
  const list = data ?? [];
  return (
    <div className="p-4 sm:p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight">Rate My Teachers</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-6">Tell the school how your teachers are doing. You can change your rating any time.</p>
      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : error ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 px-6 text-center text-slate-500 text-sm">
          {(error as any)?.response?.data?.detail ?? "Could not load your teachers."}
        </div>
      ) : list.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 px-6 text-center text-slate-400">
          <Star size={30} className="mx-auto mb-2 opacity-40" />
          <p className="font-semibold text-slate-500">No teachers to rate yet</p>
          <p className="text-sm mt-1">Your teachers appear here once your class timetable is set up.</p>
        </div>
      ) : (
        <div className="space-y-4">{list.map((t) => <TeacherCard key={t.teacher_id} t={t} />)}</div>
      )}
    </div>
  );
}
