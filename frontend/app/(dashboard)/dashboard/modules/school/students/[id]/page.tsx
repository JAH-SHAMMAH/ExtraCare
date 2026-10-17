"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Edit2, Trash2, Loader2, Phone, Mail, MapPin, Cake, GraduationCap, Users, CalendarDays } from "lucide-react";
import { useStudent, useDeleteStudent } from "@/hooks/useSchool";
import { StudentAvatar } from "@/components/students/StudentAvatar";
import { cn, formatDate } from "@/lib/utils";

function Field({ icon: Icon, label, value }: { icon?: any; label: string; value?: string | null }) {
  return (
    <div className="flex items-start gap-3 py-3">
      {Icon && <Icon size={15} className="text-slate-400 mt-0.5 shrink-0" />}
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
        <p className="text-sm text-slate-800 mt-0.5 break-words">{value || "—"}</p>
      </div>
    </div>
  );
}

export default function StudentProfilePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: s, isLoading, isError } = useStudent(id);
  const remove = useDeleteStudent();

  if (isLoading) return <div className="p-8 flex justify-center text-slate-400"><Loader2 className="animate-spin" /></div>;
  if (isError || !s) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <Link href="/dashboard/modules/school/students" className="text-sm text-brand-700 font-semibold flex items-center gap-1.5"><ArrowLeft size={14} /> Students</Link>
        <p className="mt-6 text-slate-500">We couldn&apos;t find this student.</p>
      </div>
    );
  }

  const name = `${s.first_name} ${s.last_name}`;
  const onRemove = () => {
    if (confirm(`Remove ${name} from the school roll?`)) {
      remove.mutate(s.id, { onSuccess: () => router.push("/dashboard/modules/school/students") });
    }
  };

  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/students" className="text-sm text-brand-700 font-semibold flex items-center gap-1.5 mb-5"><ArrowLeft size={14} /> All students</Link>

      <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center gap-5">
        <StudentAvatar name={name} url={s.avatar_url} size={96} className="rounded-2xl" />
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">{name}</h1>
          <p className="text-sm text-slate-500 mt-1">
            {s.class_name || "No class assigned"} · <span className="font-mono">{s.student_id}</span>
          </p>
          <span className={cn("badge mt-2 inline-flex", s.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200")}>
            {s.is_active ? "Active" : s.withdrawal_date ? "Withdrawn" : "Inactive"}
          </span>
        </div>
        <div className="flex gap-2">
          <Link href={`/dashboard/modules/school/students?edit=${s.id}`} className="btn-secondary gap-2"><Edit2 size={14} /> Edit profile</Link>
          <button onClick={onRemove} disabled={remove.isPending} className="btn-secondary gap-2 text-red-600 hover:bg-red-50"><Trash2 size={14} /> Remove</button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4 mt-4">
        <div className="bg-white rounded-2xl border border-slate-200 px-5 divide-y divide-slate-100">
          <p className="text-sm font-bold text-slate-800 pt-4 pb-2">Student details</p>
          <Field icon={GraduationCap} label="Class" value={s.class_name} />
          <Field icon={Users} label="Gender" value={s.gender ? s.gender[0].toUpperCase() + s.gender.slice(1) : null} />
          <Field icon={Cake} label="Date of birth" value={s.date_of_birth ? formatDate(s.date_of_birth) : null} />
          <Field icon={CalendarDays} label="Admitted" value={s.admission_date ? formatDate(s.admission_date) : formatDate(s.created_at)} />
          <Field icon={Mail} label="Email" value={s.email} />
          <Field icon={Phone} label="Phone" value={s.phone} />
          <Field icon={MapPin} label="Address" value={s.address} />
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 px-5 divide-y divide-slate-100 self-start">
          <p className="text-sm font-bold text-slate-800 pt-4 pb-2">Parent / guardian</p>
          <Field label="Name" value={s.guardian_name} />
          <Field label="Relationship" value={s.guardian_relationship} />
          <Field icon={Phone} label="Phone" value={s.guardian_phone} />
          <Field icon={Mail} label="Email" value={s.guardian_email} />
        </div>
      </div>
    </div>
  );
}
