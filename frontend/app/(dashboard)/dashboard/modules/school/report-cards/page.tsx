"use client";

import { useState, useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { useStudents, useReportCard, useSaveReportMeta, useSaveDomainRatings, useClasses } from "@/hooks/useSchool";
import { useTermState, useTermNames, useGradingScales, useSections, useTerms } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { useAuthStore } from "@/lib/store";
import { cn, getInitials } from "@/lib/utils";
import Link from "next/link";
import { FileText, Search, Printer, Loader2, Pencil, X, ClipboardCheck, GraduationCap, ArrowLeft, MessageSquare, Workflow } from "lucide-react";
import { PrintLetterhead } from "@/components/branding/Brand";
import { ReportCardViewer } from "@/components/reports/ReportCardViewer";

import type { Student, ReportCardDomain, SchoolClass, SchoolSection } from "@/types";

export default function ReportCardsPage() {
  // Branch on the STAFF scope, not a role slug: slugs are per-org and a cloned
  // role gets a suffixed one ("parent-boarding"), which a slug test misses and
  // drops into the teacher desk. A pupil, a parent and any clone of either hold
  // only school:reports:own:read -- the same test the sidebar and the API use.
  const isStaff = useHasPermission("school:reports:read");

  if (!isStaff) {
    return <OwnReportCardsView />;
  }

  return <TeacherReportCardsView />;
}

// ── Own view (pupil or parent): the designed report card, one component for both ──

function OwnReportCardsView() {
  const { activeRole } = useAuthStore();
  // The report-card endpoint keys on Student.id, NOT User.id. /school/students is
  // ownership-scoped for a non-staff caller: a pupil gets exactly one row (theirs),
  // a parent gets their linked children.
  const { data: studentData, isLoading } = useStudents();
  const children = (studentData?.items ?? []) as Student[];
  const people = children.map((c) => ({ id: c.id, name: `${c.first_name} ${c.last_name}`, first_name: c.first_name }));
  const isParent = activeRole === "parent" || children.length > 1;

  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      <div className="mb-6 no-print">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">{isParent ? "Report Cards" : "My Report Card"}</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">{isParent ? "Report Cards" : "My Report Card"}</h1>
        <p className="text-slate-500 text-sm mt-0.5">{isParent ? "View and print your child's report card." : "View and print your report card."}</p>
      </div>
      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : people.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <GraduationCap size={34} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-slate-500">No student record found</p>
          <p className="text-sm mt-1">Ask the school to link your account to a student.</p>
        </div>
      ) : (
        <ReportCardViewer people={people} />
      )}
    </div>
  );
}


// ── Teacher/Admin view: multi-student interface (original) ──

function TeacherReportCardsView() {
  const params = useSearchParams();
  // R4: a level-scoped view when the sidebar links here as ?section=<Name>
  // (Nursery / Primary / Secondary). Absent → the all-levels report desk.
  const sectionName = params.get("section") || "";
  const [search, setSearch] = useState("");
  const [classId, setClassId] = useState("");
  const [selectedStudent, setSelectedStudent] = useState("");
  const [pickedStudent, setPickedStudent] = useState<Student | null>(null);

  const { data: sections = [] } = useSections();
  const section = useMemo(
    () => sections.find((s: SchoolSection) => s.name.toLowerCase() === sectionName.toLowerCase()),
    [sections, sectionName],
  );
  const scoped = !!sectionName;
  // The section ROW is still called Primary / Early Years; the reports call them Junior / Nursery.
  const levelLabel = ({ primary: "Junior", "early years": "Nursery" } as Record<string, string>)[sectionName.toLowerCase()] ?? sectionName;
  // Classes belonging to this level (for the class sub-filter).
  const { data: classesResp } = useClasses({ page_size: 100 });
  const levelClasses = useMemo(
    () => (classesResp?.items || []).filter((c: SchoolClass) => !section || c.section_id === section.id),
    [classesResp, section],
  );
  // Reset the picked class/student when switching level.
  useEffect(() => { setClassId(""); setSelectedStudent(""); }, [sectionName]);

  const { data: students, isLoading: studentsLoading } = useStudents({
    search: search || undefined,
    section_id: scoped ? section?.id : undefined,
    class_id: classId || undefined,
    page_size: 50,
  });

  // A scoped view can't resolve students until its section is known.
  const items = scoped && !section ? [] : (students?.items || []);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8 no-print">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span>{scoped && <><span>Reports</span><span>/</span></>}<span className="text-brand-600 font-semibold">{scoped ? `${levelLabel} School Report` : "Report Cards"}</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">{scoped && <GraduationCap size={22} className="text-brand-600" />}{scoped ? `${levelLabel} School Report` : "Report Cards"}</h1>
        <p className="text-slate-500 text-sm mt-0.5">{scoped ? `View, complete and print report cards for the ${levelLabel} level.` : "View, complete and print student report cards."}</p>
      </div>

      {scoped && !section && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800 no-print">
          No managed section named <strong>{sectionName}</strong> yet. Create it under <span className="font-semibold">School Setup → Report Config</span> (or run the standard setup) so classes can be linked to this level.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Student list (on a phone it gives way to the report once one is picked) */}
        <div className={cn("no-print", selectedStudent && "hidden lg:block")}>
          <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 space-y-2">
            <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search students..." className="input pl-9" /></div>
            {scoped && (
              <select value={classId} onChange={(e) => { setClassId(e.target.value); setSelectedStudent(""); }} className="input">
                <option value="">All classes in {sectionName}</option>
                {levelClasses.map((c: SchoolClass) => (<option key={c.id} value={c.id}>{c.name}</option>))}
              </select>
            )}
          </div>
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden max-h-[600px] overflow-y-auto">
            {studentsLoading ? Array.from({ length: 8 }).map((_, i) => (<div key={i} className="px-4 py-3 border-b border-slate-50"><div className="h-4 bg-slate-100 rounded animate-pulse w-32" /></div>))
            : items.length === 0 ? (<div className="p-8 text-center text-slate-400 text-sm">No students found.</div>)
            : items.map((s: Student) => (
              <button key={s.id} onClick={() => { setSelectedStudent(s.id); setPickedStudent(s); window.scrollTo({ top: 0 }); }} className={cn("w-full flex items-center gap-3 px-4 py-3 border-b border-slate-50 hover:bg-slate-50 transition-colors text-left", selectedStudent === s.id && "bg-brand-50 border-brand-100")}>
                <div className="w-8 h-8 rounded-lg bg-indigo-600/10 flex items-center justify-center text-indigo-700 text-xs font-bold shrink-0">{getInitials(`${s.first_name} ${s.last_name}`)}</div>
                <div className="min-w-0"><p className="text-sm font-medium text-slate-900 truncate">{s.first_name} {s.last_name}</p><p className="text-xs text-slate-400">{s.student_id}</p></div>
              </button>
            ))}
          </div>
        </div>

        {/* Report card — the same designed report parents and pupils see */}
        <div className={cn("lg:col-span-2", !selectedStudent && "hidden lg:block")}>
          {selectedStudent && (
            <div className="no-print mb-4 space-y-3">
              <button onClick={() => { setSelectedStudent(""); setPickedStudent(null); }} className="lg:hidden inline-flex items-center gap-1.5 text-sm font-semibold text-brand-600"><ArrowLeft size={15} /> All students</button>
              <div className="bg-white rounded-xl border border-slate-200 p-3 flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-widest text-slate-400 mr-1">Edit</span>
                <Link href="/dashboard/modules/school/make-report" className="btn-secondary gap-2 text-xs py-1.5"><Pencil size={13} /> Marks</Link>
                <Link href="/dashboard/modules/school/teacher-comments" className="btn-secondary gap-2 text-xs py-1.5"><MessageSquare size={13} /> Comments</Link>
                <Link href="/dashboard/modules/school/report-workflow" className="btn-secondary gap-2 text-xs py-1.5"><Workflow size={13} /> Approval &amp; publish</Link>
              </div>
            </div>
          )}
          {!selectedStudent ? (
            <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><FileText size={40} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">Select a student</p><p className="text-sm mt-1">Choose a student from the list to view their report card.</p></div>
          ) : (
            <>
              <ReportCardViewer
                key={selectedStudent}
                people={pickedStudent && pickedStudent.id === selectedStudent ? [{ id: pickedStudent.id, name: `${pickedStudent.first_name} ${pickedStudent.last_name}`, first_name: pickedStudent.first_name }] : []}
              />
              <p className="text-xs text-slate-400 mt-3 no-print">
                To change what appears here: scores in <strong>Make Report</strong>, comments in <strong>Teacher Comments</strong>, ratings and achievements in <strong>Skills &amp; Behaviour / Learning Goals</strong>.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ReportCardView({ card, term, studentId, canWrite }: { card: any; term: string; studentId: string; canWrite: boolean }) {
  const [editing, setEditing] = useState(false);
  const [rating, setRating] = useState(false);
  const subjects: any[] = card.subjects || [];
  const domains: ReportCardDomain[] = card.domains || [];
  const hasAttendance = card.attendance_total != null;

  return (
    <div>
      {/* Staff-only controls (never printed) */}
      {canWrite && (
        <div className="flex justify-end gap-2 mb-3 no-print">
          {domains.length > 0 && (
            <button onClick={() => { setRating((v) => !v); setEditing(false); }} className="btn-secondary gap-2 text-xs py-1.5">
              {rating ? <><X size={13} /> Close</> : <><ClipboardCheck size={13} /> Enter assessment ratings</>}
            </button>
          )}
          <button onClick={() => { setEditing((v) => !v); setRating(false); }} className="btn-secondary gap-2 text-xs py-1.5">
            {editing ? <><X size={13} /> Close</> : <><Pencil size={13} /> Edit report details</>}
          </button>
        </div>
      )}
      {editing && canWrite && <ReportMetaForm card={card} term={term} studentId={studentId} onDone={() => setEditing(false)} />}
      {rating && canWrite && <DomainRatingsForm domains={domains} term={term} studentId={studentId} onDone={() => setRating(false)} />}

      <PrintLetterhead title="Report Card" subtitle={`${card.term || term}${card.academic_year ? ` — ${card.academic_year}` : ""}`} />

      {/* Header */}
      <div className="text-center mb-5 pb-4 border-b border-slate-100">
        <h2 className="text-lg font-bold text-slate-900">{card.student?.first_name} {card.student?.last_name}</h2>
        <p className="text-sm text-slate-500">
          {/* The class NAME only. `card.section` is the ARM, not the school
              section, and the name already carries it for 24 of 31 classes
              ("Year 1 A") -- so this printed "Year 1 A · Year 1 · Section A" on
              a parent's card, and gave the 6 Early Years classes an arm Educare
              does not give them at all. The level is dropped with it: for a
              class named "Year 1 A" it restates the name. */}
          {card.class_name || "—"}
        </p>
        <p className="text-xs text-slate-400 mt-0.5">{card.term || term}{card.academic_year ? ` — ${card.academic_year}` : ""}</p>
      </div>

      {/* Marks table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left mb-5">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Subject", "CA (40)", "Exam (60)", "Total", "Grade", "Remarks", "Teacher"].map((h) => (
                <th key={h} className="px-3 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {subjects.length === 0 ? (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-sm text-slate-400">No grades recorded for this term.</td></tr>
            ) : subjects.map((s, i) => (
              <tr key={i}>
                <td className="px-3 py-2.5 text-sm font-medium text-slate-800">{s.subject_name || "—"}</td>
                <td className="px-3 py-2.5 text-sm text-slate-600 tabular-nums">{s.ca_score ?? "—"}</td>
                <td className="px-3 py-2.5 text-sm text-slate-600 tabular-nums">{s.exam_score ?? "—"}</td>
                <td className="px-3 py-2.5 text-sm font-semibold text-slate-900 tabular-nums">{s.total ?? "—"}</td>
                <td className="px-3 py-2.5"><span className="badge bg-brand-50 text-brand-700 border-brand-200">{s.grade || "—"}</span></td>
                <td className="px-3 py-2.5 text-xs text-slate-500">{s.remarks || "—"}</td>
                <td className="px-3 py-2.5 text-xs text-slate-500">{s.teacher_name || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Assessment domains (EYFS / skills / Cambridge) — R3 */}
      <DomainReportBlock domains={domains} />

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-slate-50 rounded-lg">
        <div><p className="text-[10px] font-bold uppercase text-slate-400">Total</p><p className="text-lg font-bold text-slate-900 tabular-nums">{card.total_score ?? "—"}</p></div>
        <div><p className="text-[10px] font-bold uppercase text-slate-400">Average</p><p className="text-lg font-bold text-slate-900 tabular-nums">{card.average != null ? Number(card.average).toFixed(1) : "—"}</p></div>
        <div><p className="text-[10px] font-bold uppercase text-slate-400">Position</p><p className="text-lg font-bold text-slate-900 tabular-nums">{card.position || "—"}{card.class_size ? ` / ${card.class_size}` : ""}</p></div>
        <div><p className="text-[10px] font-bold uppercase text-slate-400">Attendance</p><p className="text-lg font-bold text-slate-900 tabular-nums">{hasAttendance ? `${card.attendance_present ?? 0} / ${card.attendance_total}` : "—"}</p>{hasAttendance && card.attendance_absent != null && <p className="text-[10px] text-slate-400">{card.attendance_absent} absent</p>}</div>
      </div>

      {/* Comments + next term */}
      {(card.teacher_remark || card.principal_remark || card.next_term_begins) && (
        <div className="mt-4 space-y-2">
          {card.teacher_remark && (<div className="p-3 bg-blue-50 rounded-lg"><p className="text-[10px] font-bold uppercase text-blue-500">Class Teacher&apos;s Comment</p><p className="text-sm text-blue-800">{card.teacher_remark}</p></div>)}
          {card.principal_remark && (<div className="p-3 bg-purple-50 rounded-lg"><p className="text-[10px] font-bold uppercase text-purple-500">Head Teacher&apos;s Comment</p><p className="text-sm text-purple-800">{card.principal_remark}</p></div>)}
          {card.next_term_begins && (<p className="text-sm text-slate-600"><span className="font-semibold">Next term begins:</span> {card.next_term_begins}</p>)}
        </div>
      )}
    </div>
  );
}

function ReportMetaForm({ card, term, studentId, onDone }: { card: any; term: string; studentId: string; onDone: () => void }) {
  const save = useSaveReportMeta();
  const [form, setForm] = useState({
    class_teacher_comment: card.teacher_remark || "",
    head_teacher_comment: card.principal_remark || "",
    attendance_present: card.attendance_present ?? "",
    attendance_total: card.attendance_total ?? "",
    next_term_begins: card.next_term_begins || "",
  });
  // Re-seed when switching student/term.
  useEffect(() => {
    setForm({
      class_teacher_comment: card.teacher_remark || "",
      head_teacher_comment: card.principal_remark || "",
      attendance_present: card.attendance_present ?? "",
      attendance_total: card.attendance_total ?? "",
      next_term_begins: card.next_term_begins || "",
    });
  }, [studentId, term]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = () => {
    save.mutate({
      student_id: studentId, term,
      data: {
        class_teacher_comment: form.class_teacher_comment || null,
        head_teacher_comment: form.head_teacher_comment || null,
        attendance_present: form.attendance_present === "" ? null : Number(form.attendance_present),
        attendance_total: form.attendance_total === "" ? null : Number(form.attendance_total),
        next_term_begins: form.next_term_begins || null,
      },
    }, { onSuccess: onDone });
  };

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 mb-5 no-print">
      <h3 className="text-sm font-bold text-slate-800 mb-4">Report details — {term}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2"><label className="label">Class teacher&apos;s comment</label><textarea value={form.class_teacher_comment} onChange={(e) => setForm({ ...form, class_teacher_comment: e.target.value })} className="input" rows={2} /></div>
        <div className="md:col-span-2"><label className="label">Head teacher&apos;s comment</label><textarea value={form.head_teacher_comment} onChange={(e) => setForm({ ...form, head_teacher_comment: e.target.value })} className="input" rows={2} /></div>
        <div><label className="label">Days present</label><input type="number" min={0} value={form.attendance_present} onChange={(e) => setForm({ ...form, attendance_present: e.target.value })} className="input" /></div>
        <div><label className="label">Total school days</label><input type="number" min={0} value={form.attendance_total} onChange={(e) => setForm({ ...form, attendance_total: e.target.value })} className="input" /></div>
        <div><label className="label">Next term begins</label><input type="date" value={form.next_term_begins} onChange={(e) => setForm({ ...form, next_term_begins: e.target.value })} className="input" /></div>
      </div>
      <div className="flex justify-end gap-3 mt-4">
        <button onClick={onDone} className="btn-secondary">Cancel</button>
        <button onClick={submit} disabled={save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save details</button>
      </div>
    </div>
  );
}

// ── R3 assessment domains: partitioning shared by the printed block + entry form ──

const SKILL_GROUPS: { type: string; label: string }[] = [
  { type: "psychomotor", label: "Psychomotor Skills" },
  { type: "affective", label: "Affective Traits" },
];

function partition(domains: ReportCardDomain[]) {
  const byPos = (a: ReportCardDomain, b: ReportCardDomain) => a.position - b.position || a.name.localeCompare(b.name);
  const areas = domains.filter((d) => d.domain_type === "eyfs_area").sort(byPos);
  const goals = domains.filter((d) => d.domain_type === "eyfs_goal").sort(byPos);
  const strands = domains.filter((d) => d.domain_type === "cambridge_strand").sort(byPos);
  const skills = SKILL_GROUPS.map((g) => ({ ...g, rows: domains.filter((d) => d.domain_type === g.type).sort(byPos) })).filter((g) => g.rows.length);
  const strandsBySubject: Record<string, ReportCardDomain[]> = {};
  strands.forEach((s) => { const k = s.subject_name || "Cambridge"; (strandsBySubject[k] ||= []).push(s); });
  return { areas, goals, strands, strandsBySubject, skills, any: domains.length > 0 };
}

function RatingRow({ name, rating }: { name: string; rating: string | null }) {
  return (
    <tr>
      <td className="px-3 py-2 text-sm text-slate-700">{name}</td>
      <td className="px-3 py-2 text-sm text-right">{rating ? <span className="badge bg-brand-50 text-brand-700 border-brand-200">{rating}</span> : <span className="text-slate-300">—</span>}</td>
    </tr>
  );
}

function DomainReportBlock({ domains }: { domains: ReportCardDomain[] }) {
  const { areas, goals, strandsBySubject, skills, any } = partition(domains);
  if (!any) return null;
  return (
    <div className="mb-5 space-y-5">
      {/* EYFS Areas of Learning + Early Learning Goals */}
      {areas.length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2">Areas of Learning (EYFS)</h3>
          <div className="space-y-3">
            {areas.map((area) => {
              const g = goals.filter((x) => x.parent_domain_id === area.domain_id);
              return (
                <div key={area.domain_id} className="border border-slate-100 rounded-lg overflow-hidden">
                  <div className="bg-slate-50/80 px-3 py-2 text-sm font-semibold text-slate-800 flex items-center justify-between">
                    <span>{area.name}</span>{area.rating && !g.length && <span className="badge bg-brand-50 text-brand-700 border-brand-200">{area.rating}</span>}
                  </div>
                  {g.length > 0 && (
                    <table className="w-full"><tbody className="divide-y divide-slate-50">{g.map((goal) => <RatingRow key={goal.domain_id} name={goal.name} rating={goal.rating} />)}</tbody></table>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Cambridge attainment, grouped by subject */}
      {Object.keys(strandsBySubject).length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2">Cambridge Attainment</h3>
          <div className="border border-slate-100 rounded-lg overflow-hidden">
            <table className="w-full"><tbody className="divide-y divide-slate-50">
              {Object.entries(strandsBySubject).map(([subject, rows]) => rows.map((s, i) => (
                <RatingRow key={s.domain_id} name={i === 0 && rows.length > 1 ? `${subject}` : (rows.length > 1 ? s.name : subject)} rating={s.rating} />
              )))}
            </tbody></table>
          </div>
        </div>
      )}

      {/* Nigerian psychomotor + affective */}
      {skills.map((g) => (
        <div key={g.type}>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2">{g.label}</h3>
          <div className="border border-slate-100 rounded-lg overflow-hidden">
            <table className="w-full"><tbody className="divide-y divide-slate-50">{g.rows.map((r) => <RatingRow key={r.domain_id} name={r.name} rating={r.rating} />)}</tbody></table>
          </div>
        </div>
      ))}
    </div>
  );
}

function DomainRatingsForm({ domains, term, studentId, onDone }: { domains: ReportCardDomain[]; term: string; studentId: string; onDone: () => void }) {
  const save = useSaveDomainRatings();
  // This page is the LEGACY, name-based report card (useTermState holds "Autumn",
  // not an id), but ratings are keyed by term_id since migration 130. Resolve the
  // name here rather than thread term_id through the whole legacy page.
  const { data: terms = [] } = useTerms();
  const termId = useMemo(
    () => (terms as any[]).find((t) => t.name === term)?.id as string | undefined,
    [terms, term],
  );
  const { data: scales = [] } = useGradingScales();
  const scaleOptions = useMemo(() => {
    const m = new Map<string, string[]>();
    scales.forEach((s: any) => m.set(s.id, (s.bands || []).map((b: any) => b.grade)));
    return m;
  }, [scales]);

  const seed = () => domains.map((d) => ({ domain_id: d.domain_id, rating: d.rating || "", comment: d.comment || "" }));
  const [rows, setRows] = useState<{ domain_id: string; rating: string; comment: string }[]>(seed);
  useEffect(() => { setRows(seed()); }, [studentId, term]); // eslint-disable-line react-hooks/exhaustive-deps

  const setRow = (id: string, patch: Partial<{ rating: string; comment: string }>) =>
    setRows((rs) => rs.map((r) => (r.domain_id === id ? { ...r, ...patch } : r)));
  const val = (id: string) => rows.find((r) => r.domain_id === id) || { rating: "", comment: "" };

  const submit = () => {
    if (!termId) return;   // the button is disabled without it; belt and braces
    save.mutate(
      { student_id: studentId, data: { term_id: termId, ratings: rows.map((r) => ({ domain_id: r.domain_id, rating: r.rating || null, comment: r.comment || null })) } },
      { onSuccess: onDone },
    );
  };

  const { areas, goals, strands, skills } = partition(domains);
  const flat: { header: string; items: ReportCardDomain[] }[] = [];
  areas.forEach((a) => flat.push({ header: a.name, items: goals.filter((g) => g.parent_domain_id === a.domain_id) || [] }));
  // Areas with no goals are rated directly.
  areas.filter((a) => !goals.some((g) => g.parent_domain_id === a.domain_id)).forEach((a) => { const grp = flat.find((f) => f.header === a.name); if (grp) grp.items = [a]; });
  skills.forEach((g) => flat.push({ header: g.label, items: g.rows }));
  if (strands.length) flat.push({ header: "Cambridge Attainment", items: strands });

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 mb-5 no-print">
      <h3 className="text-sm font-bold text-slate-800 mb-1">Assessment ratings — {term}</h3>
      <p className="text-xs text-slate-500 mb-4">Rate each domain against the section&apos;s descriptor scale. Leave a domain blank to clear it.</p>
      <div className="space-y-5 max-h-[460px] overflow-y-auto pr-1">
        {flat.map((group) => (
          <div key={group.header}>
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 mb-2">{group.header}</p>
            <div className="space-y-2">
              {group.items.map((d) => {
                const opts = d.rating_scale_id ? scaleOptions.get(d.rating_scale_id) : undefined;
                const v = val(d.domain_id);
                return (
                  <div key={d.domain_id} className="grid grid-cols-1 md:grid-cols-3 gap-2 items-center">
                    <span className="text-sm text-slate-700 md:col-span-1">{d.name}</span>
                    {opts && opts.length ? (
                      <select value={v.rating} onChange={(e) => setRow(d.domain_id, { rating: e.target.value })} className="input">
                        <option value="">— Not rated —</option>
                        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
                      </select>
                    ) : (
                      <input value={v.rating} onChange={(e) => setRow(d.domain_id, { rating: e.target.value })} className="input" placeholder="Rating" />
                    )}
                    <input value={v.comment} onChange={(e) => setRow(d.domain_id, { comment: e.target.value })} className="input" placeholder="Comment (optional)" />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="flex justify-end gap-3 mt-4">
        <button onClick={onDone} className="btn-secondary">Cancel</button>
        <button onClick={submit} disabled={save.isPending || !termId} className="btn-primary gap-2" title={!termId ? `No academic term named "${term}" is configured` : undefined}>{save.isPending && <Loader2 size={15} className="animate-spin" />}Save ratings</button>
      </div>
    </div>
  );
}
