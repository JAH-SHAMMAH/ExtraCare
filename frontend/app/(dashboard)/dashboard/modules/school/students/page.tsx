"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useStudents, useCreateStudent, useUpdateStudent, useDeleteStudent, useClasses, useYearGroups } from "@/hooks/useSchool";
import { useSections } from "@/hooks/usePlatform";
import { uploadApi, schoolApi } from "@/lib/api";
import { StudentAvatar } from "@/components/students/StudentAvatar";
import { cn, formatDate } from "@/lib/utils";
import Link from "next/link";
import { Search, UserPlus, GraduationCap, Edit2, Trash2, X, Loader2, Eye, Upload, Camera, User as MaleIcon, UserRound as FemaleIcon, Users, UserCheck, UserX } from "lucide-react";
import { toast } from "sonner";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { Skeleton } from "@/components/loading/Skeleton";
import type { Student } from "@/types";

export default function StudentsPage() {
  const canImport = useHasPermission("school:write");
  const [search, setSearch] = useState("");
  // Filters can arrive on the URL (the dashboard cards deep-link here).
  const qs = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const [roster, setRoster] = useState<"all" | "active" | "inactive">(
    qs.get("status") === "active" ? "active" : qs.get("status") === "inactive" ? "inactive" : "all");
  const [sectionId, setSectionId] = useState(qs.get("section_id") || "");
  const [yearGroup, setYearGroup] = useState(qs.get("year_group") || "");
  const [classId, setClassId] = useState(qs.get("class_id") || "");
  const [gender, setGender] = useState(qs.get("gender") || "");
  const { data: sections } = useSections();
  const { data: yearGroups } = useYearGroups(sectionId || undefined);
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [editingStudent, setEditingStudent] = useState<Student | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const { data: classData } = useClasses({ page_size: 100, section_id: sectionId || undefined, year_group: yearGroup || undefined });
  const classOptions: { id: string; name: string }[] = (classData?.items ?? (Array.isArray(classData) ? classData : []))
    .slice().sort((a: any, b: any) => String(a.name).localeCompare(String(b.name), undefined, { numeric: true }));

  const { data, isLoading } = useStudents({
    page, page_size: 25, search: search || undefined, status: roster === "all" ? undefined : roster,
    section_id: sectionId || undefined, year_group: yearGroup || undefined,
    class_id: classId || undefined, gender: gender || undefined,
  });
  const schoolName = (sections ?? []).find((x: any) => x.id === sectionId)?.name;
  // Only show the skeleton after 300ms of loading — sub-300ms responses
  // render straight to data with no flicker.
  const showSkeleton = useDelayedFlag(isLoading);
  // True school-wide totals (not just the 25 rows on this page).
  const { data: allCount } = useStudents({ page: 1, page_size: 1 });
  const { data: activeCount } = useStudents({ page: 1, page_size: 1, status: "active" });
  const { data: inactiveCount } = useStudents({ page: 1, page_size: 1, status: "inactive" });
  const createStudent = useCreateStudent();
  const updateStudent = useUpdateStudent();
  const deleteStudent = useDeleteStudent();

  const [form, setForm] = useState({
    first_name: "", last_name: "", student_id: "", email: "", phone: "",
    date_of_birth: "", gender: "male", class_id: "",
    guardian_name: "", guardian_phone: "", address: "",
  });

  const resetForm = () => {
    setForm({ first_name: "", last_name: "", student_id: "", email: "", phone: "", date_of_birth: "", gender: "male", class_id: "", guardian_name: "", guardian_phone: "", address: "" });
    setEditingStudent(null);
    setPhotoUrl("");
    setShowForm(false);
  };

  const handleSubmit = () => {
    // Trim + presence check before we fire the request. The backend also
    // validates, but catching it here means no round-trip and no toast for
    // the common "forgot the first name" case.
    const required: Array<keyof typeof form> = ["first_name", "last_name", "student_id"];
    const missing = required.filter((k) => !(form[k] || "").toString().trim());
    if (missing.length) {
      const labels: Record<string, string> = {
        first_name: "First Name",
        last_name: "Last Name",
        student_id: "Student ID",
      };
      toast.error(`Please fill: ${missing.map((k) => labels[k]).join(", ")}`);
      return;
    }
    if (editingStudent) {
      updateStudent.mutate({ id: editingStudent.id, data: { ...form, photo_url: photoUrl || null } }, { onSuccess: resetForm });
    } else {
      createStudent.mutate({ ...form, photo_url: photoUrl || null }, { onSuccess: resetForm });
    }
  };

  const handleEdit = (s: Student) => {
    setForm({
      first_name: s.first_name, last_name: s.last_name, student_id: s.student_id,
      email: s.email || "", phone: s.phone || "", date_of_birth: s.date_of_birth || "",
      gender: s.gender || "male", class_id: s.class_id || "",
      guardian_name: s.guardian_name || "", guardian_phone: s.guardian_phone || "", address: s.address || "",
    });
    setEditingStudent(s);
    setPhotoUrl(s.avatar_url || "");
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Deep link from the profile page: /students?edit=<id> opens that student's edit form.
  useEffect(() => {
    const editParam = new URLSearchParams(window.location.search).get("edit");
    if (!editParam) return;
    schoolApi.students.get(editParam).then((st: Student) => handleEdit(st)).catch(() => toast.error("Couldn't open that student."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDelete = (s: Student) => {
    if (confirm(`Remove ${s.first_name} ${s.last_name} from the school roll? This can't be undone from here.`)) {
      deleteStudent.mutate(s.id);
    }
  };

  const handlePhoto = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) { toast.error("Photo must be under 25MB."); return; }
    setUploading(true);
    try {
      const r = await uploadApi.studentPhoto(file);
      setPhotoUrl(r.url);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Couldn't upload the photo.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Students</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Student Management</h1>
          <p className="text-slate-500 text-sm mt-0.5">Manage student records, enrolment, and profiles.</p>
        </div>
        <div className="flex items-center gap-2">
          {canImport && (
            <Link href="/dashboard/modules/school/students/import" className="btn-secondary gap-2">
              <Upload size={15} />
              Import CSV
            </Link>
          )}
          <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2">
            <UserPlus size={15} />
            Add Student
          </button>
        </div>
      </div>

      {/* Stats — coloured, and each tile filters the list below */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {([
          { label: "Total Students", value: allCount?.total ?? "—", icon: Users, g: "from-emerald-500 to-green-700", on: () => { setRoster("all"); setPage(1); } },
          { label: "Active", value: activeCount?.total ?? "—", icon: UserCheck, g: "from-sky-500 to-blue-700", on: () => { setRoster("active"); setPage(1); } },
          { label: "Inactive", value: inactiveCount?.total ?? "—", icon: UserX, g: "from-slate-500 to-slate-700", on: () => { setRoster("inactive"); setPage(1); } },
          { label: "Classes", value: classOptions.length || "—", icon: GraduationCap, g: "from-violet-500 to-indigo-700", on: () => { window.location.href = "/dashboard/modules/school/classes"; } },
        ] as const).map(({ label, value, icon: Icon, g, on }) => (
          <button key={label} type="button" onClick={on}
            className={cn("relative overflow-hidden rounded-2xl bg-gradient-to-br p-4 text-left text-white shadow-md transition hover:-translate-y-0.5 hover:shadow-xl", g)}>
            <Icon size={64} className="pointer-events-none absolute -right-2 -bottom-2 opacity-15" aria-hidden />
            <p className="text-[11px] font-bold uppercase tracking-widest text-white/90">{label}</p>
            <p className="relative text-3xl font-black tabular-nums mt-1">{value}</p>
          </button>
        ))}
      </div>

      {/* Create/Edit Form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editingStudent ? "Edit Student" : "New Student"}</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="flex items-center gap-4 mb-5">
            <StudentAvatar name={`${form.first_name} ${form.last_name}`.trim() || "Student"} url={photoUrl} size={72} />
            <div>
              <label className="btn-secondary gap-2 cursor-pointer inline-flex">
                {uploading ? <Loader2 size={14} className="animate-spin" /> : <Camera size={14} />}
                {photoUrl ? "Change photo" : "Add photo"}
                <input type="file" accept="image/*" className="hidden" onChange={handlePhoto} disabled={uploading} />
              </label>
              {photoUrl && <button type="button" onClick={() => setPhotoUrl("")} className="ml-3 text-xs text-slate-500 hover:text-red-600">Remove photo</button>}
              <p className="text-[11px] text-slate-400 mt-1">JPG or PNG, up to 5MB.</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">First Name *</label><input required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} className="input" /></div>
            <div><label className="label">Last Name *</label><input required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} className="input" /></div>
            <div><label className="label">Student ID *</label><input required value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} placeholder="STU001" className="input" /></div>
            <div><label className="label">Email</label><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="input" /></div>
            <div><label className="label">Phone</label><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+234..." className="input" /></div>
            <div><label className="label">Date of Birth</label><input type="date" value={form.date_of_birth} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} className="input" /></div>
            <div>
              <label className="label">Gender</label>
              <select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} className="input">
                <option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="label">Class</label>
              <select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} className="input">
                <option value="">No class yet</option>
                {classOptions.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div><label className="label">Guardian Name</label><input value={form.guardian_name} onChange={(e) => setForm({ ...form, guardian_name: e.target.value })} className="input" /></div>
            <div><label className="label">Guardian Phone</label><input value={form.guardian_phone} onChange={(e) => setForm({ ...form, guardian_phone: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Address</label><input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={createStudent.isPending || updateStudent.isPending} className="btn-primary gap-2">
              {(createStudent.isPending || updateStudent.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editingStudent ? "Update" : "Add Student"}
            </button>
          </div>
        </div>
      )}

      {/* Select school / year group / class — Educare's "Select School to View Students" */}
      <div className="rounded-xl border border-emerald-800/30 overflow-hidden mb-4 bg-white shadow-sm">
        <div className="bg-emerald-700 text-white px-5 py-3 flex items-center justify-between gap-3 flex-wrap">
          <h2 className="font-bold tracking-wide">Select School to View Students</h2>
          <div className="flex bg-white/15 rounded-lg p-0.5 shrink-0">
            {([["all", "All"], ["active", "Active"], ["inactive", "Inactive"]] as const).map(([val, label]) => (
              <button key={val} onClick={() => { setRoster(val); setPage(1); }}
                className={cn("px-3 py-1.5 text-xs font-semibold rounded-md transition-colors",
                  roster === val ? "bg-white text-emerald-800 shadow" : "text-white/90 hover:bg-white/10")}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="label">Select School</label>
            <select value={sectionId} onChange={(e) => { setSectionId(e.target.value); setYearGroup(""); setClassId(""); setPage(1); }} className="input">
              <option value="">All schools</option>
              {(sections ?? []).map((x: any) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Select Year Group</label>
            <select value={yearGroup} onChange={(e) => { setYearGroup(e.target.value); setClassId(""); setPage(1); }} className="input">
              <option value="">All year groups</option>
              {(yearGroups ?? []).map((y: any) => <option key={y.id} value={y.name}>{y.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Class</label>
            <select value={classId} onChange={(e) => { setClassId(e.target.value); setPage(1); }} className="input">
              <option value="">All classes</option>
              {classOptions.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Gender</label>
            <select value={gender} onChange={(e) => { setGender(e.target.value); setPage(1); }} className="input">
              <option value="">All</option><option value="male">Male</option><option value="female">Female</option>
            </select>
          </div>
        </div>
        <div className="px-5 pb-5 flex flex-wrap gap-3">
          <button type="button" onClick={() => { setGender(gender === "male" ? "" : "male"); setPage(1); }}
            className={cn("inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-bold text-white bg-gradient-to-r from-sky-500 to-blue-700 shadow", gender === "male" && "ring-2 ring-offset-2 ring-sky-500")}>
            <MaleIcon size={16} /> No of Male(s): {data?.male ?? "—"}
          </button>
          <button type="button" onClick={() => { setGender(gender === "female" ? "" : "female"); setPage(1); }}
            className={cn("inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-bold text-white bg-gradient-to-r from-pink-500 to-rose-700 shadow", gender === "female" && "ring-2 ring-offset-2 ring-rose-500")}>
            <FemaleIcon size={16} /> No of Female(s): {data?.female ?? "—"}
          </button>
        </div>
      </div>

      <div className="bg-emerald-700 text-white rounded-t-xl px-5 py-3">
        <h3 className="font-bold tracking-wide">
          Student Information Section{schoolName ? ` For ${schoolName.toUpperCase()}` : ""}
          {yearGroup ? ` · ${yearGroup}` : ""}
        </h3>
      </div>
      <div className="bg-white border border-t-0 border-slate-200 rounded-b-xl p-3 mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-64">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search by name, ID..." className="input pl-9" />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                {["#", "Profile Data", "Surname", "First Name", "Parent / Guardian", "Address", "Class", "Actions"].map((h) => (
                  <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {showSkeleton ? (
                Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} cols={8} />)
              ) : isLoading ? null : (
                data?.items?.map((s: Student, idx: number) => (
                  <tr key={s.id} className="align-top odd:bg-white even:bg-slate-50/60 hover:bg-emerald-50/40 transition-colors">
                    <td className="px-4 py-4 text-sm text-slate-500">{(page - 1) * 25 + idx + 1}</td>
                    <td className="px-4 py-4">
                      <div className="flex flex-col items-center gap-1.5 w-32 text-center">
                        <StudentPhotoCell student={s} canWrite={canImport} size={104} />
                        <span className="text-xs font-mono font-semibold text-slate-700">{s.student_id}</span>
                        <span className="text-[11px] text-slate-500">Phone: {s.phone || s.guardian_phone || "—"}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-sm font-bold uppercase text-slate-900">
                      <Link href={`/dashboard/modules/school/students/${s.id}`} className="hover:text-emerald-700">{s.last_name}</Link>
                    </td>
                    <td className="px-4 py-4 text-sm font-semibold uppercase text-slate-800">{s.first_name}</td>
                    <td className="px-4 py-4 text-sm text-slate-700 min-w-44">
                      <p className="font-semibold uppercase">{s.guardian_name || "—"}</p>
                      {s.guardian_email && <p className="text-xs text-slate-500 break-all">{s.guardian_email}</p>}
                      {s.guardian_phone && <p className="text-xs text-slate-500">{s.guardian_phone}</p>}
                    </td>
                    <td className="px-4 py-4 text-xs uppercase text-slate-600 min-w-40">{s.address || "—"}</td>
                    <td className="px-4 py-4">
                      <span className="inline-block rounded-lg bg-emerald-50 border border-emerald-200 px-2 py-1 text-xs font-bold uppercase text-emerald-800">{s.class_name || "No class"}</span>
                      {!s.is_active && <span className="block mt-1 text-[10px] font-bold uppercase text-slate-500">Inactive</span>}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-col gap-1.5 w-28">
                        <Link href={`/dashboard/modules/school/students/${s.id}`} title="View full profile" aria-label={`View ${s.first_name} ${s.last_name}'s profile`} className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-600"><Eye size={13} /> Details</Link>
                        <button onClick={() => handleEdit(s)} title="Edit profile" aria-label={`Edit ${s.first_name} ${s.last_name}`} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-300"><Edit2 size={13} /> Edit</button>
                        <button onClick={() => handleDelete(s)} title="Remove student" aria-label={`Remove ${s.first_name} ${s.last_name}`} className="inline-flex items-center gap-1.5 rounded-lg bg-red-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-600"><Trash2 size={13} /> Delete</button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {data && data.total_pages > 1 && (
          <div className="px-5 py-4 border-t border-slate-100 flex items-center justify-between">
            <p className="text-xs text-slate-500">Showing {(page - 1) * 25 + 1}–{Math.min(page * 25, data.total)} of {data.total}</p>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-40">Prev</button>
              <button onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))} disabled={page === data.total_pages} className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}

        {!isLoading && (!data?.items || data.items.length === 0) && (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <GraduationCap size={40} className="mb-3 opacity-40" />
            <p className="font-semibold">No students found</p>
            <p className="text-sm mt-1">Add your first student to get started.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr className="border-b border-slate-50">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-5 py-4">
          <Skeleton className={i === 0 ? "h-4 w-36" : i === cols - 1 ? "h-4 w-10" : "h-4 w-24"} />
        </td>
      ))}
    </tr>
  );
}


/** Large photo with a camera button, so the photo can be set straight from the list. */
function StudentPhotoCell({ student, canWrite, size = 44 }: { student: Student; canWrite: boolean; size?: number }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const set = useMutation({
    mutationFn: async (file: File) => {
      const { url } = await uploadApi.studentPhoto(file);
      return schoolApi.students.update(student.id, { photo_url: url });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["students"] }); toast.success("Photo updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Photo upload failed."),
  });
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <StudentAvatar name={`${student.first_name} ${student.last_name}`} url={student.avatar_url} size={size} />
      {canWrite && (
        <>
          <button type="button" onClick={() => input.current?.click()} disabled={set.isPending}
            title={student.avatar_url ? "Change photo" : "Set photo"} aria-label="Set student photo"
            className="absolute -bottom-1.5 -right-1.5 w-7 h-7 rounded-full bg-emerald-700 text-white flex items-center justify-center shadow ring-2 ring-white disabled:opacity-100">
            {set.isPending ? <Loader2 size={13} className="animate-spin" /> : <Camera size={13} />}
          </button>
          <input ref={input} type="file" accept="image/*" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) set.mutate(f); e.target.value = ""; }} />
        </>
      )}
    </div>
  );
}
