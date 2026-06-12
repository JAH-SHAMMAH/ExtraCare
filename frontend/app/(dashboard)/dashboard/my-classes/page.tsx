"use client";

import Link from "next/link";
import {
  School, BookOpen, ArrowRight, Calendar, ClipboardList, Award, AlertCircle,
} from "lucide-react";
import { useMyContexts } from "@/hooks/useMyContexts";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { TableSkeleton } from "@/components/loading/Skeleton";

/**
 * Teacher portal: focused view of the classes + subjects the user teaches.
 * A lighter, read-forward alternative to /modules/school/classes (which is
 * the admin-heavy CRUD grid). Teachers land here to answer "what do I teach
 * and where do I go next?"
 */
export default function MyClassesPage() {
  const { data, isLoading } = useMyContexts();
  const showSkeleton = useDelayedFlag(isLoading);

  const teacher = data?.as_teacher;
  const classes = teacher?.classes ?? [];
  const subjects = teacher?.subjects ?? [];
  const today = teacher?.today_slots ?? [];

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Teacher</span><span>/</span>
          <span className="text-brand-600 font-semibold">My Classes</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Classes</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Classes and subjects assigned to you, plus today&apos;s lessons.
        </p>
      </div>

      {showSkeleton ? (
        <TableSkeleton rows={3} cols={4} />
      ) : classes.length === 0 && subjects.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          {/* Today */}
          <section className="bg-white rounded-xl border border-slate-200 overflow-hidden mb-6">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-800">Today&apos;s lessons</h2>
              <Link href="/dashboard/modules/school/timetable" className="text-xs text-brand-600 font-semibold hover:underline flex items-center gap-1">
                Full timetable <ArrowRight size={12} />
              </Link>
            </div>
            {today.length === 0 ? (
              <div className="px-5 py-8 text-center text-sm text-slate-400">
                No lessons scheduled for today.
              </div>
            ) : (
              <div className="divide-y divide-slate-50">
                {today.map((slot) => (
                  <div key={slot.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 transition-colors">
                    <div className="text-xs font-bold text-slate-500 tabular-nums w-20">
                      {slot.start_time}–{slot.end_time}
                    </div>
                    <div className="w-1 h-10 rounded bg-brand-400" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-slate-900 truncate">{slot.subject_name ?? "Lesson"}</p>
                      <p className="text-xs text-slate-500">{slot.room ? `Room ${slot.room}` : "—"}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Classes + Subjects side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Classes */}
            <section className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-100">
                <h2 className="text-sm font-bold text-slate-800">Classes I teach ({classes.length})</h2>
              </div>
              <div className="divide-y divide-slate-50">
                {classes.length === 0 ? (
                  <div className="px-5 py-8 text-center text-sm text-slate-400">
                    You aren&apos;t assigned to any classes as the form teacher.
                  </div>
                ) : (
                  classes.map((c) => (
                    <div key={c.id} className="flex items-center gap-3 px-5 py-3.5">
                      <div className="w-10 h-10 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center shrink-0">
                        <School size={15} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-slate-900 truncate">{c.name}</p>
                        <p className="text-xs text-slate-500 truncate">
                          {[c.level, c.academic_year, c.room ? `Room ${c.room}` : null].filter(Boolean).join(" · ")}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <Link
                          href={`/dashboard/modules/school/attendance`}
                          title="Mark attendance"
                          className="p-2 rounded-lg text-slate-400 hover:text-brand-600 hover:bg-slate-50"
                        >
                          <ClipboardList size={14} />
                        </Link>
                        <Link
                          href={`/dashboard/modules/school/grades`}
                          title="Grade submissions"
                          className="p-2 rounded-lg text-slate-400 hover:text-brand-600 hover:bg-slate-50"
                        >
                          <Award size={14} />
                        </Link>
                        <Link
                          href={`/dashboard/modules/school/timetable`}
                          title="View timetable"
                          className="p-2 rounded-lg text-slate-400 hover:text-brand-600 hover:bg-slate-50"
                        >
                          <Calendar size={14} />
                        </Link>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </section>

            {/* Subjects */}
            <section className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-100">
                <h2 className="text-sm font-bold text-slate-800">Subjects I teach ({subjects.length})</h2>
              </div>
              <div className="divide-y divide-slate-50">
                {subjects.length === 0 ? (
                  <div className="px-5 py-8 text-center text-sm text-slate-400">
                    No subjects assigned to you yet.
                  </div>
                ) : (
                  subjects.map((s) => (
                    <Link
                      key={s.id}
                      href={`/dashboard/modules/school/subjects`}
                      className="flex items-center gap-3 px-5 py-3.5 hover:bg-slate-50 transition-colors"
                    >
                      <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
                        <BookOpen size={15} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-slate-900 truncate">{s.name}</p>
                        <p className="text-xs text-slate-500 truncate">{s.code ?? "No code"}</p>
                      </div>
                      <ArrowRight size={14} className="text-slate-300" />
                    </Link>
                  ))
                )}
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-10 text-center">
      <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
        <AlertCircle size={26} className="text-slate-400" />
      </div>
      <h2 className="text-base font-bold text-slate-800 mb-1">Not assigned to any classes</h2>
      <p className="text-sm text-slate-500 max-w-md mx-auto">
        Ask an administrator to assign you to a class or subject to see your teaching schedule here.
      </p>
    </div>
  );
}
