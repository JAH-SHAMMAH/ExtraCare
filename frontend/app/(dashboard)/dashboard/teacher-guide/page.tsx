import { BookOpen } from "lucide-react";
import { TEACHER_GUIDE } from "@/lib/teacherGuide";

export default function TeacherGuidePage() {
  return (
    <div className="p-4 sm:p-8 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-1">
        <BookOpen className="text-emerald-600" size={24} />
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Teacher Quick Guide</h1>
      </div>
      <p className="text-slate-500 text-sm mb-6">How to get the most from the portal, in the order you will need it.</p>
      <div className="space-y-4">
        {TEACHER_GUIDE.map((s, i) => (
          <section key={s.title} className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="font-bold text-slate-900 mb-2"><span className="text-emerald-600 mr-2">{i + 1}.</span>{s.title}</h2>
            <ul className="space-y-2 text-sm text-slate-700 list-disc pl-5">
              {s.points.map((p) => <li key={p}>{p}</li>)}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
