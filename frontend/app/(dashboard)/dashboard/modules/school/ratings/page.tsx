"use client";

import { useState } from "react";
import { useTeachers, useTeacherRatings, useSubmitRating } from "@/hooks/useSchool";
import { cn, getInitials } from "@/lib/utils";
import { Star, Search, Loader2, Send } from "lucide-react";
import type { Teacher, TeacherRating } from "@/types";

function StarRating({ value, onChange, readonly = false }: { value: number; onChange?: (v: number) => void; readonly?: boolean }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <button key={star} onClick={() => !readonly && onChange?.(star)} className={cn("transition-colors", readonly ? "cursor-default" : "cursor-pointer hover:text-amber-400")}>
          <Star size={16} className={cn(star <= value ? "fill-amber-400 text-amber-400" : "text-slate-300")} />
        </button>
      ))}
    </div>
  );
}

export default function RatingsPage() {
  const [search, setSearch] = useState("");
  const [selectedTeacher, setSelectedTeacher] = useState("");
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [studentId, setStudentId] = useState("");

  const { data: teachers, isLoading: teachersLoading } = useTeachers({ search: search || undefined });
  const { data: ratings, isLoading: ratingsLoading } = useTeacherRatings({ teacher_id: selectedTeacher || undefined });
  const submitRating = useSubmitRating();

  const teacherList = teachers?.items || [];
  const ratingList = ratings?.items || (Array.isArray(ratings) ? ratings : []);
  const avgRating = ratingList.length > 0 ? ratingList.reduce((s: number, r: TeacherRating) => s + r.rating, 0) / ratingList.length : 0;

  const handleSubmit = () => {
    if (!selectedTeacher || !rating || !studentId) return;
    submitRating.mutate({ teacher_id: selectedTeacher, student_id: studentId, rating, comment }, { onSuccess: () => { setRating(0); setComment(""); } });
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Teacher Ratings</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Teacher Ratings</h1>
        <p className="text-slate-500 text-sm mt-0.5">Student-to-teacher rating system for feedback.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Teacher list */}
        <div>
          <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4">
            <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search teachers..." className="input pl-9" /></div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden max-h-[500px] overflow-y-auto">
            {teachersLoading ? Array.from({ length: 5 }).map((_, i) => (<div key={i} className="px-4 py-3 border-b border-slate-50"><div className="h-4 bg-slate-100 rounded animate-pulse w-32" /></div>))
            : teacherList.length === 0 ? (<div className="p-8 text-center text-slate-400 text-sm">No teachers found.</div>)
            : teacherList.map((t: Teacher) => (
              <button key={t.id} onClick={() => setSelectedTeacher(t.id)} className={cn("w-full flex items-center gap-3 px-4 py-3 border-b border-slate-50 hover:bg-slate-50 transition-colors text-left", selectedTeacher === t.id && "bg-brand-50 border-brand-100")}>
                <div className="w-8 h-8 rounded-lg bg-emerald-600/10 flex items-center justify-center text-emerald-700 text-xs font-bold shrink-0">{getInitials(`${t.first_name} ${t.last_name}`)}</div>
                <div className="min-w-0 flex-1"><p className="text-sm font-medium text-slate-900 truncate">{t.first_name} {t.last_name}</p><p className="text-xs text-slate-400">{t.department || "No department"}</p></div>
              </button>
            ))}
          </div>
        </div>

        {/* Ratings panel */}
        <div className="lg:col-span-2 space-y-6">
          {!selectedTeacher ? (
            <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><Star size={40} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">Select a teacher</p><p className="text-sm mt-1">Choose a teacher to view and submit ratings.</p></div>
          ) : (
            <>
              {/* Average */}
              <div className="bg-white rounded-xl border border-slate-200 p-6 flex items-center gap-6">
                <div className="text-center"><p className="text-3xl font-black text-slate-900">{avgRating.toFixed(1)}</p><StarRating value={Math.round(avgRating)} readonly /><p className="text-xs text-slate-400 mt-1">{ratingList.length} rating{ratingList.length !== 1 ? "s" : ""}</p></div>
                <div className="flex-1 space-y-1">
                  {[5, 4, 3, 2, 1].map((n) => { const count = ratingList.filter((r: TeacherRating) => r.rating === n).length; const pct = ratingList.length > 0 ? (count / ratingList.length) * 100 : 0; return (
                    <div key={n} className="flex items-center gap-2"><span className="text-xs text-slate-500 w-3">{n}</span><div className="flex-1 bg-slate-100 rounded-full h-2"><div className="bg-amber-400 rounded-full h-full" style={{ width: `${pct}%` }} /></div><span className="text-xs text-slate-400 w-6">{count}</span></div>
                  ); })}
                </div>
              </div>

              {/* Submit */}
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="text-sm font-bold text-slate-800 mb-4">Submit Rating</h3>
                <div className="space-y-3">
                  <div><label className="label">Your Student ID *</label><input value={studentId} onChange={(e) => setStudentId(e.target.value)} placeholder="Enter your student ID" className="input" /></div>
                  <div><label className="label">Rating *</label><StarRating value={rating} onChange={setRating} /></div>
                  <div><label className="label">Comment</label><textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Optional feedback..." className="input min-h-[80px] resize-none" /></div>
                  <button onClick={handleSubmit} disabled={submitRating.isPending || !rating || !studentId} className="btn-primary gap-2">{submitRating.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}Submit Rating</button>
                </div>
              </div>

              {/* Existing ratings */}
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="text-sm font-bold text-slate-800 mb-4">Recent Ratings</h3>
                {ratingsLoading ? (<div className="text-center py-4"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>)
                : ratingList.length === 0 ? (<p className="text-sm text-slate-400 text-center py-4">No ratings yet.</p>)
                : (<div className="space-y-3">{ratingList.slice(0, 10).map((r: TeacherRating) => (
                  <div key={r.id} className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                    <div className="flex items-center justify-between mb-1"><StarRating value={r.rating} readonly /><span className="text-[10px] text-slate-400">{r.student_name || r.student_id}</span></div>
                    {r.comment && <p className="text-xs text-slate-600">{r.comment}</p>}
                  </div>
                ))}</div>)}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
